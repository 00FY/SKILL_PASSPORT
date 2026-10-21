import re
import json
import hashlib
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from pydantic import BaseModel, Field

from .allowlist import safe_fetch_issuer_page


class IssuerRecord(BaseModel):
    issuer_name: str
    recipient_name: Optional[str] = None
    credential_title: Optional[str] = None
    issue_date: Optional[str] = None
    credential_id: Optional[str] = None
    verify_url: str
    raw_evidence_hash: str
    fetch_timestamp: str
    is_valid: bool = True
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


COURSERA_DATE_RE = re.compile(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}\b",
                              re.IGNORECASE)
# The line after the course title: "has successfully completed", "an online non-credit course authorized by ...",
# "an online specialization authorized by ...", "... offered through Coursera"
COURSERA_MARKER_RE = re.compile(
    r"has successfully completed|authorized by|offered through coursera|^an online\b|^a(?:n)?\s+(?:professional|guided)",
    re.IGNORECASE)
NOT_A_NAME_WORDS = {"coursera", "certificate", "course", "university", "specialization", "verify", "completed",
                    "online", "authorized", "professional", "instructor", "director", "signature", "www", "http",
                    "for", "and", "with", "the", "to", "in", "on", "introduction", "fundamentals", "foundations"}


def looks_like_person_name(text: Optional[str]) -> bool:
    """2-5 words of letters (names like "O'Neil", "Jean-Luc", "A. Smith" allowed), no digits or certificate words."""
    if not text:
        return False
    words = text.strip().split()
    if not 2 <= len(words) <= 5 or any(ch.isdigit() for ch in text):
        return False
    if any(w.lower().strip(".,") in NOT_A_NAME_WORDS for w in words):
        return False
    return all(re.fullmatch(r"[^\W\d_][\w.'\-]*", w) for w in words)


def parse_coursera_certificate_lines(lines: List[str]) -> Dict[str, Optional[str]]:
    """
    Recipient, course title and date from the text lines of a Coursera certificate PDF. Layouts vary
    ("an online non-credit course authorized by ...", a leading date line, a logo line), so lines are
    matched by what they contain, never by position alone.
    """
    issue_date = next((m.group(0) for l in lines for m in [COURSERA_DATE_RE.search(l)] if m), None)
    content = [l for l in lines if not (COURSERA_DATE_RE.search(l) and len(l) <= 20)]  # drop date-only lines
    recipient = title = None
    marker = next((i for i, l in enumerate(content) if COURSERA_MARKER_RE.search(l)), -1)
    completed_line = marker >= 0 and "has successfully completed" in content[marker].lower()
    if completed_line and marker >= 1 and looks_like_person_name(content[marker - 1]):
        # "<name>" / "has successfully completed" / "<course>"
        recipient = content[marker - 1]
        title = content[marker + 1] if marker + 1 < len(content) else None
    elif marker >= 2 and looks_like_person_name(content[marker - 2]):
        # "<name>" / "<course>" / "an online ... authorized by ..."
        recipient, title = content[marker - 2], content[marker - 1]
    else:
        for i, l in enumerate(content):
            if looks_like_person_name(l):
                recipient = l
                nxt = content[i + 1] if i + 1 < len(content) else None
                if nxt and not COURSERA_MARKER_RE.search(nxt):
                    title = nxt
                break
    return {"recipient_name": recipient, "course_title": title, "issue_date": issue_date}


def compute_evidence_hash(content: bytes) -> str:
    """Computes SHA-256 fingerprint of the raw evidence record received from the issuer."""
    return hashlib.sha256(content).hexdigest()


class BaseIssuerAdapter:
    def can_handle(self, url: str) -> bool:
        raise NotImplementedError

    def fetch_and_parse(self, url: str) -> IssuerRecord:
        raise NotImplementedError


class CourseraAdapter(BaseIssuerAdapter):
    """
    Adapter for Coursera verify URLs:
    e.g. https://www.coursera.org/verify/<ID> or https://www.coursera.org/account/accomplishments/verify/<ID>
    """
    def can_handle(self, url: str) -> bool:
        lower = url.lower()
        return "coursera.org" in lower and any(p in lower for p in ["/verify", "/accomplishments", "/certificate", "/specialization"])

    def fetch_and_parse(self, url: str) -> IssuerRecord:
        now_ts = datetime.now(timezone.utc).isoformat()
        try:
            status, raw_bytes, html, final_url = safe_fetch_issuer_page(url)
        except Exception as exc:
            return IssuerRecord(
                issuer_name="Coursera",
                verify_url=url,
                raw_evidence_hash=compute_evidence_hash(b""),
                fetch_timestamp=now_ts,
                is_valid=False,
                error_message=f"Failed to fetch Coursera verify page: {exc}"
            )

        ev_hash = compute_evidence_hash(raw_bytes)

        if status == 404 or "couldn't find a certificate" in html.lower() or "page not found" in html.lower():
            return IssuerRecord(
                issuer_name="Coursera",
                verify_url=final_url,
                raw_evidence_hash=ev_hash,
                fetch_timestamp=now_ts,
                is_valid=False,
                error_message="Coursera certificate record not found (404/invalid code)"
            )

        # Extract Credential ID from URL
        cred_id = None
        id_match = re.search(r"/(?:verify|certificate|records|specialization|professional-cert)/(?:certificate/)?([A-Za-z0-9\-]+)", final_url)
        if not id_match:
            id_match = re.search(r"/(?:verify|certificate|records|specialization|professional-cert)/(?:certificate/)?([A-Za-z0-9\-]+)", url)
        if id_match:
            cred_id = id_match.group(1)

        recipient_name = None
        course_title = None
        issue_date = None

        from .matching import GENERIC_TITLES

        # 1. Specialization REST API check (for Coursera Specializations)
        if cred_id and re.match(r"^[A-Za-z0-9]{8,35}$", cred_id):
            s12n_api_url = (
                f"https://www.coursera.org/api/onDemandSpecializationMemberships.v1/"
                f"?q=byCode&code={cred_id}&fields=userId,s12nId,onDemandSpecializations.v1(name,slug,courseIds,metadata)&includes=signatureTrackProfile,s12nId"
            )
            try:
                s_status, s_bytes, s_text, _ = safe_fetch_issuer_page(s12n_api_url)
                if s_status == 200 and s_text:
                    s_data = json.loads(s_text)
                    linked = s_data.get("linked", {})
                    profiles = linked.get("signatureTrackProfilesV1", [])
                    s12ns = linked.get("onDemandSpecializationsV1", [])
                    if profiles:
                        p = profiles[0]
                        fn = str(p.get("firstName") or "").strip()
                        ln = str(p.get("lastName") or "").strip()
                        if fn and ln and not any(w in fn.lower() for w in ["coursera", "user"]):
                            recipient_name = f"{fn} {ln}".strip()
                    if s12ns:
                        cand_title = str(s12ns[0].get("name") or "").strip()
                        if cand_title and cand_title.lower() not in GENERIC_TITLES:
                            course_title = cand_title
            except Exception as exc:
                logger.debug("Coursera Specialization API query failed for %s: %s", cred_id, exc)

        # 2. Try Coursera official PDF endpoint if cred_id is available (Course Certificates)
        if (not course_title or not recipient_name) and cred_id and re.match(r"^[A-Za-z0-9]{8,25}$", cred_id):
            pdf_api_url = f"https://www.coursera.org/api/certificate.v1/pdf/{cred_id}"
            try:
                p_status, p_bytes, _, _ = safe_fetch_issuer_page(pdf_api_url)
                if p_status == 200 and p_bytes.startswith(b"%PDF") and len(p_bytes) > 2000:
                    import pymupdf
                    pdf_doc = pymupdf.open("pdf", p_bytes)
                    pdf_lines = [l.strip() for page in pdf_doc for l in page.get_text().splitlines() if l.strip()]
                    parsed = parse_coursera_certificate_lines(pdf_lines)
                    issue_date = issue_date or parsed["issue_date"]
                    recipient_name = recipient_name or parsed["recipient_name"]
                    course_title = course_title or parsed["course_title"]
            except Exception as exc:
                logger.debug("Failed to fetch/parse Coursera official PDF for %s: %s", cred_id, exc)

        # 3. Check window.__APOLLO_STATE__ in HTML (authoritative React state for both Courses and Specializations)
        if not recipient_name or not course_title:
            apollo_m = re.search(r'window\.__APOLLO_STATE__\s*=\s*(\{.+?\});', html)
            if apollo_m:
                try:
                    state = json.loads(apollo_m.group(1))
                    def walk(obj):
                        nonlocal recipient_name, course_title, issue_date
                        if isinstance(obj, dict):
                            if not recipient_name and "firstName" in obj and "lastName" in obj:
                                fn = str(obj.get("firstName") or "").strip()
                                ln = str(obj.get("lastName") or "").strip()
                                if fn and ln and not any(w in fn.lower() for w in ["coursera", "user", "student"]):
                                    recipient_name = f"{fn} {ln}".strip()
                            if not issue_date and "grantedAt" in obj and isinstance(obj["grantedAt"], (int, float)):
                                try:
                                    dt = datetime.fromtimestamp(obj["grantedAt"] / 1000.0, timezone.utc)
                                    issue_date = dt.strftime("%B %d, %Y")
                                except Exception:
                                    pass
                            t_type = obj.get("__typename", "")
                            if not course_title and t_type in ("Course_Course", "AccomplishmentsOnDemandSpecialization", "OnDemandSpecialization", "XdpV1"):
                                cand = obj.get("name")
                                if cand and isinstance(cand, str) and cand.strip().lower() not in GENERIC_TITLES:
                                    course_title = cand.strip()
                            for v in obj.values():
                                walk(v)
                        elif isinstance(obj, list):
                            for item in obj:
                                walk(item)
                    walk(state)
                except Exception as exc:
                    logger.debug("Error walking Coursera Apollo state: %s", exc)

        # 4. Check JSON-LD in HTML
        if not recipient_name or not course_title:
            jsonld_matches = re.findall(r'<script\s+type=[\"\']application/ld\+json[\"\'][^>]*>(.*?)</script>', html, re.DOTALL | re.IGNORECASE)
            for j_str in jsonld_matches:
                try:
                    data = json.loads(j_str.strip())
                    if isinstance(data, dict):
                        if "recipient" in data and isinstance(data["recipient"], dict):
                            recipient_name = data["recipient"].get("name") or recipient_name
                        if "name" in data and not course_title:
                            course_title = data.get("name")
                        if "dateCreated" in data or "datePublished" in data:
                            issue_date = data.get("dateCreated") or data.get("datePublished") or issue_date
                except Exception:
                    pass

        # 5. Check OpenGraph / Meta tags
        if not course_title or not recipient_name:
            m = re.search(r'<meta[^>]+(?:property|name)=[\"\'](?:og:title|twitter:title)[\"\'][^>]+content=[\"\']([^\"\']+)[\"\']', html, re.IGNORECASE)
            if m:
                meta_title = m.group(1).strip()
                if meta_title.lower().startswith("completion certificate for "):
                    cand_t = meta_title[len("completion certificate for "):].strip()
                    if cand_t and not course_title and cand_t.lower() not in GENERIC_TITLES:
                        course_title = cand_t
                comp_match = re.search(r"^([A-Za-z\s\.\-]{2,40}?)\s+(?:has\s+completed|completed|earned)\s+(.+)", meta_title, re.IGNORECASE)
                if comp_match:
                    if not recipient_name:
                        recipient_name = comp_match.group(1).strip()
                    if not course_title:
                        cand_meta = comp_match.group(2).strip()
                        if cand_meta.lower() not in GENERIC_TITLES:
                            course_title = cand_meta

        # 6. Check date fallback
        if not issue_date:
            date_m = re.search(r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b", html, re.IGNORECASE)
            if date_m:
                issue_date = date_m.group(0)

        # 7. Filter generic titles and boilerplate
        if course_title and course_title.lower().strip() in GENERIC_TITLES:
            course_title = None

        if recipient_name and (recipient_name.lower().strip() in GENERIC_TITLES or "coursera" in recipient_name.lower()):
            recipient_name = None
        # Never report a date or a course line as the recipient: without a believable name the result is
        # "pending manual check", not a mismatch
        if recipient_name and not looks_like_person_name(recipient_name):
            recipient_name = None
        if course_title and looks_like_person_name(course_title) and course_title == recipient_name:
            course_title = None

        return IssuerRecord(
            issuer_name="Coursera",
            recipient_name=recipient_name,
            credential_title=course_title,
            issue_date=issue_date,
            credential_id=cred_id,
            verify_url=final_url,
            raw_evidence_hash=ev_hash,
            fetch_timestamp=now_ts,
            is_valid=True,
            metadata={"status_code": status}
        )


class CredlyAdapter(BaseIssuerAdapter):
    """
    Adapter for Credly public badge pages:
    e.g. https://www.credly.com/badges/<uuid>/public_url or https://www.credly.com/badges/<uuid>
    """
    def can_handle(self, url: str) -> bool:
        lower = url.lower()
        return "credly.com" in lower and "/badges/" in lower

    def fetch_and_parse(self, url: str) -> IssuerRecord:
        now_ts = datetime.now(timezone.utc).isoformat()
        try:
            status, raw_bytes, html, final_url = safe_fetch_issuer_page(url)
        except Exception as exc:
            return IssuerRecord(
                issuer_name="Credly",
                verify_url=url,
                raw_evidence_hash=compute_evidence_hash(b""),
                fetch_timestamp=now_ts,
                is_valid=False,
                error_message=f"Failed to fetch Credly badge page: {exc}"
            )

        ev_hash = compute_evidence_hash(raw_bytes)

        # Check for error view or unverified status
        if status == 404 or "unable to verify badge" in html.lower() or "error-view__title" in html.lower():
            return IssuerRecord(
                issuer_name="Credly",
                verify_url=final_url,
                raw_evidence_hash=ev_hash,
                fetch_timestamp=now_ts,
                is_valid=False,
                error_message="Badge not found or unable to verify on Credly"
            )

        # Extract UUID from URL
        cred_id = None
        uuid_m = re.search(r"/badges/([a-f0-9\-]{8,40})", final_url, re.IGNORECASE)
        if uuid_m:
            cred_id = uuid_m.group(1)

        recipient_name = None
        badge_title = None
        issue_date = None
        issuer_org = "Credly"

        # 1. Parse OpenGraph / Twitter meta tags
        # Pattern in Credly: <meta property="og:title" content="[Name] earned [Badge Name] from [Issuer]">
        m = re.search(r'<meta[^>]+(?:property|name)=[\"\'](?:og:title|twitter:title)[\"\'][^>]+content=[\"\']([^\"\']+)[\"\']', html, re.IGNORECASE)
        if m:
            meta_title = m.group(1)
            # Check pattern: "John Doe earned AWS Certified Solutions Architect - Associate from Amazon Web Services"
            earned_m = re.search(r"^(.+?)\s+earned\s+(.+?)(?:\s+from\s+(.+))?$", meta_title, re.IGNORECASE)
            if earned_m:
                recipient_name = earned_m.group(1).strip()
                badge_title = earned_m.group(2).strip()
                if earned_m.group(3):
                    issuer_org = earned_m.group(3).strip()
            elif not badge_title:
                badge_title = meta_title.replace(" | Credly", "").strip()

        # 2. Check JSON-LD
        jsonld_matches = re.findall(r'<script\s+type=[\"\']application/ld\+json[\"\'][^>]*>(.*?)</script>', html, re.DOTALL | re.IGNORECASE)
        for j_str in jsonld_matches:
            try:
                data = json.loads(j_str.strip())
                if isinstance(data, dict):
                    if "recipient" in data:
                        recipient_name = data["recipient"].get("name") or recipient_name
                    if "name" in data and not badge_title:
                        badge_title = data["name"]
                    if "issuer" in data:
                        if isinstance(data["issuer"], dict):
                            issuer_org = data["issuer"].get("name") or issuer_org
                        elif isinstance(data["issuer"], str):
                            issuer_org = data["issuer"]
                    if "issueDate" in data:
                        issue_date = data["issueDate"]
            except Exception:
                pass

        # 3. HTML markup fallback
        if not recipient_name:
            # Look for: Issued to <a ...>Name</a> or <div class="earner-name">
            rec_m = re.search(r"(?:issued\s+to|recipient)[\s:]*<[^>]+>?\s*([A-Za-z\s\.\-]{2,40})", html, re.IGNORECASE)
            if rec_m:
                recipient_name = rec_m.group(1).strip()

        if not issue_date:
            date_m = re.search(r"(?:issued\s+on|issue\s+date)[\s:]*([A-Za-z0-9\s\,]{4,25})", html, re.IGNORECASE)
            if date_m:
                issue_date = date_m.group(1).strip()

        return IssuerRecord(
            issuer_name=issuer_org if issuer_org != "Credly" else "Credly",
            recipient_name=recipient_name,
            credential_title=badge_title,
            issue_date=issue_date,
            credential_id=cred_id,
            verify_url=final_url,
            raw_evidence_hash=ev_hash,
            fetch_timestamp=now_ts,
            is_valid=True,
            metadata={"status_code": status, "platform": "Credly"}
        )


class NptelAdapter(BaseIssuerAdapter):
    """
    Adapter for NPTEL / Swayam certificate verify pages:
    e.g. https://nptel.ac.in/noc/Ecertificate/?q=<ID> or https://archive.nptel.ac.in/noc/...
    """
    def can_handle(self, url: str) -> bool:
        lower = url.lower()
        return ("nptel.ac.in" in lower or "swayam.gov.in" in lower)

    def fetch_and_parse(self, url: str) -> IssuerRecord:
        now_ts = datetime.now(timezone.utc).isoformat()
        try:
            status, raw_bytes, html, final_url = safe_fetch_issuer_page(url)
        except Exception as exc:
            return IssuerRecord(
                issuer_name="NPTEL",
                verify_url=url,
                raw_evidence_hash=compute_evidence_hash(b""),
                fetch_timestamp=now_ts,
                is_valid=False,
                error_message=f"Failed to fetch NPTEL certificate page: {exc}"
            )

        ev_hash = compute_evidence_hash(raw_bytes)

        if status == 404 or "no certificate found" in html.lower() or "invalid certificate" in html.lower():
            return IssuerRecord(
                issuer_name="NPTEL",
                verify_url=final_url,
                raw_evidence_hash=ev_hash,
                fetch_timestamp=now_ts,
                is_valid=False,
                error_message="NPTEL certificate not found"
            )

        # Extract certificate/roll ID
        cred_id = None
        id_m = re.search(r"[?&]q=([A-Za-z0-9]+)", final_url)
        if id_m:
            cred_id = id_m.group(1)

        recipient_name = None
        course_title = None
        issue_date = None
        score = None

        # Clean HTML tags to extract plain text
        clean_text = re.sub(r"<[^>]+>", " ", html)
        clean_text = re.sub(r"\s+", " ", clean_text)

        # NPTEL pages display candidate name, course name, roll number, and score
        name_m = re.search(r"(?:Name\s+of\s+Candidate|Candidate\s+Name|Name)\s*[:\-]\s*([A-Za-z\s\.\-]{2,40}?)(?:\s+(?:Course|Roll|Consolidated|Score|Marks|Date|Session)\b|$)", clean_text, re.IGNORECASE)
        if name_m:
            recipient_name = name_m.group(1).strip()

        course_m = re.search(r"(?:Course\s+Name|Course)\s*[:\-]\s*([A-Za-z0-9\s\:\,\.\-]{3,80}?)(?:\s+(?:Consolidated|Score|Marks|Roll|Date|Session|Name)\b|$)", clean_text, re.IGNORECASE)
        if course_m:
            course_title = course_m.group(1).strip()

        score_m = re.search(r"(?:Consolidated\s+Score|Total\s+Score|Score|Marks)\s*[:\-]\s*([0-9\.]+\s*(?:%|/100)?)", clean_text, re.IGNORECASE)
        if score_m:
            score = score_m.group(1).strip()

        date_m = re.search(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s*(?:-|–|\s)\s*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}\b", html, re.IGNORECASE)
        if date_m:
            issue_date = date_m.group(0)

        metadata = {"status_code": status, "platform": "NPTEL"}
        if score:
            metadata["nptel_score"] = score

        return IssuerRecord(
            issuer_name="NPTEL",
            recipient_name=recipient_name,
            credential_title=course_title,
            issue_date=issue_date,
            credential_id=cred_id,
            verify_url=final_url,
            raw_evidence_hash=ev_hash,
            fetch_timestamp=now_ts,
            is_valid=True,
            metadata=metadata
        )


class OpenBadgesAdapter(BaseIssuerAdapter):
    """
    Adapter for Open Badges 3.0 / W3C Verifiable Credentials (signed JSON).
    """
    def can_handle(self, url: str) -> bool:
        lower = url.lower()
        return lower.endswith(".json") or "/credentials/" in lower or "/badges/" in lower

    def fetch_and_parse(self, url: str) -> IssuerRecord:
        now_ts = datetime.now(timezone.utc).isoformat()
        try:
            status, raw_bytes, text, final_url = safe_fetch_issuer_page(url)
        except Exception as exc:
            return IssuerRecord(
                issuer_name="Open Badges",
                verify_url=url,
                raw_evidence_hash=compute_evidence_hash(b""),
                fetch_timestamp=now_ts,
                is_valid=False,
                error_message=f"Failed to fetch Open Badges credential: {exc}"
            )

        ev_hash = compute_evidence_hash(raw_bytes)
        try:
            data = json.loads(text)
        except Exception:
            return IssuerRecord(
                issuer_name="Open Badges",
                verify_url=final_url,
                raw_evidence_hash=ev_hash,
                fetch_timestamp=now_ts,
                is_valid=False,
                error_message="Credential payload is not valid JSON"
            )

        recipient_name = None
        if "recipient" in data:
            rec = data["recipient"]
            recipient_name = rec.get("name") or rec.get("identity") if isinstance(rec, dict) else str(rec)
        elif "credentialSubject" in data:
            cs = data["credentialSubject"]
            recipient_name = cs.get("name") if isinstance(cs, dict) else None

        badge_name = None
        if "badge" in data and isinstance(data["badge"], dict):
            badge_name = data["badge"].get("name")
        elif "name" in data:
            badge_name = data["name"]

        issue_date = data.get("issuedOn") or data.get("issuanceDate")

        return IssuerRecord(
            issuer_name="Open Badges 3.0",
            recipient_name=recipient_name,
            credential_title=badge_name,
            issue_date=issue_date,
            verify_url=final_url,
            raw_evidence_hash=ev_hash,
            fetch_timestamp=now_ts,
            is_valid=True,
            metadata={"format": "OpenBadges/W3C"}
        )


ADAPTERS = [
    CourseraAdapter(),
    CredlyAdapter(),
    NptelAdapter(),
    OpenBadgesAdapter(),
]


def get_adapter_for_url(url: str) -> Optional[BaseIssuerAdapter]:
    for adapter in ADAPTERS:
        if adapter.can_handle(url):
            return adapter
    return None
