import io
import re
import logging
from typing import List, Dict, Optional, Tuple, Set
import numpy as np
import cv2
import pymupdf

from ..skills import SKILL_CATALOG, normalize_skill

logger = logging.getLogger(__name__)

# Verification URL regex patterns
VERIFY_URL_RE = re.compile(
    r"((?:https?://)?(?:www\.)?(?:coursera\.org/(?:verify|account/accomplishments)[^\s\"'<>)]*|credly\.com/badges/[a-zA-Z0-9\-_/]+|nptel\.ac\.in/[^\s\"'<>)]*|archive\.nptel\.ac\.in/[^\s\"'<>)]*|swayam\.gov\.in/[^\s\"'<>)]*|udemy\.com/certificate/[^\s\"'<>)]*|[\w\.\-]+/verify/[^\s\"'<>)]*))",
    re.IGNORECASE
)

CREDENTIAL_ID_RE = re.compile(
    r"(?:credential\s*id|certificate\s*id|license\s*number|cert\s*#|verification\s*code|roll\s*(?:no|number)|cert\s*id|\bid)[\s:]*([A-Za-z0-9\-]{5,40})",
    re.IGNORECASE
)

DATE_PATTERNS = [
    re.compile(r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b", re.IGNORECASE),
    re.compile(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+\d{4}\b", re.IGNORECASE),
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
    re.compile(r"\b\d{1,2}/\d{1,2}/\d{4}\b"),
    re.compile(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s*(?:-|–|\s)\s*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}\b", re.IGNORECASE),
]

RECIPIENT_PATTERNS = [
    re.compile(r"(?:this\s+is\s+to\s+certify\s+that|certifies\s+that|awarded\s+to|presented\s+to|proudly\s+presented\s+to|granted\s+to)\s+([A-Za-z\.\s]{2,40}?)(?:\s+has|\s+completed|\s+successfully|\s+for|\s+on|\n|\r)", re.IGNORECASE),
    re.compile(r"(?:certificate\s+of\s+completion\s+presented\s+to)\s+([A-Za-z\.\s]{2,40})", re.IGNORECASE),
    re.compile(r"(?:Name\s+of\s+Candidate|Candidate\s+Name)\s*[:\-]\s*([A-Za-z\.\s]{2,40})", re.IGNORECASE),
]


class ExtractedPointers:
    def __init__(self):
        self.verify_urls: List[str] = []
        self.credential_ids: List[str] = []
        self.qr_code_urls: List[str] = []
        self.embedded_hyperlinks: List[str] = []
        self.raw_text: str = ""
        self.candidate_name: Optional[str] = None
        self.certificate_title: Optional[str] = None
        self.issue_date: Optional[str] = None
        self.skills: List[str] = []
        self.all_pointers: List[str] = []


class PointerExtractor:
    """
    Extracts verification pointers from PDFs or images:
    1. Printed verify URLs & credential IDs from document text
    2. Embedded hyperlinks in PDF annotation dictionaries
    3. Decoded QR codes using OpenCV
    """

    def extract(self, filename: str, contents: bytes, target_candidate_name: Optional[str] = None) -> ExtractedPointers:
        pointers = ExtractedPointers()
        lower_name = filename.lower()

        if lower_name.endswith(".pdf"):
            self._extract_from_pdf(contents, pointers)
        elif lower_name.endswith((".png", ".jpg", ".jpeg", ".webp")):
            self._extract_from_image(contents, pointers)
        else:
            try:
                pointers.raw_text = contents.decode("utf-8", errors="ignore")
            except Exception:
                pointers.raw_text = ""

        # Extract printed URLs and IDs from text
        self._extract_text_pointers(pointers)

        # Extract recipient name heuristics
        if not pointers.candidate_name:
            for rp in RECIPIENT_PATTERNS:
                m = rp.search(pointers.raw_text)
                if m:
                    cand_str = m.group(1).strip()
                    if 2 <= len(cand_str) <= 40 and not any(w in cand_str.lower() for w in ["course", "completion", "university", "online"]):
                        pointers.candidate_name = cand_str
                        break

        if not pointers.candidate_name and target_candidate_name:
            pointers.candidate_name = target_candidate_name

        # Extract title heuristics (from document text only - never from filename)
        if not pointers.certificate_title:
            pointers.certificate_title = self._extract_title(pointers.raw_text)

        # Extract date heuristics
        if not pointers.issue_date:
            for dp in DATE_PATTERNS:
                dm = dp.search(pointers.raw_text)
                if dm:
                    pointers.issue_date = dm.group(0)
                    break

        # Extract skills (from text only - never from filename)
        search_text = f"{pointers.raw_text}\n{pointers.certificate_title or ''}"
        pointers.skills = self._detect_skills(search_text)

        # Combine all pointers for transparency
        seen_ptrs = set()
        for u in pointers.qr_code_urls + pointers.embedded_hyperlinks + pointers.verify_urls + pointers.credential_ids:
            if u and u not in seen_ptrs:
                seen_ptrs.add(u)
                pointers.all_pointers.append(u)

        return pointers

    def _extract_from_pdf(self, contents: bytes, pointers: ExtractedPointers):
        try:
            doc = pymupdf.open("pdf", contents)
        except Exception as exc:
            logger.warning("Failed to open PDF with pymupdf: %s", exc)
            return

        text_pages = []
        qr_detector = cv2.QRCodeDetector()

        for page_idx in range(len(doc)):
            page = doc[page_idx]

            # 1. Text extraction
            text_pages.append(page.get_text() or "")

            # 2. Embedded hyperlink extraction
            try:
                links = page.get_links()
                for link in links:
                    uri = link.get("uri")
                    if uri and uri.startswith(("http://", "https://")):
                        clean_uri = uri.strip()
                        if clean_uri not in pointers.embedded_hyperlinks:
                            pointers.embedded_hyperlinks.append(clean_uri)
            except Exception as exc:
                logger.debug("Error extracting PDF links on page %d: %s", page_idx, exc)

            # 3. QR code extraction via page rendering (up to 3 pages)
            if page_idx < 3:
                try:
                    pix = page.get_pixmap(dpi=150)
                    img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
                    if pix.n == 4:
                        cv_img = cv2.cvtColor(img_array, cv2.COLOR_RGBA2BGR)
                    else:
                        cv_img = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)

                    # Detect single QR
                    val, pts, _ = qr_detector.detectAndDecode(cv_img)
                    if val and val.strip():
                        qr_val = val.strip()
                        if qr_val not in pointers.qr_code_urls:
                            pointers.qr_code_urls.append(qr_val)

                    # Also try multi QR
                    ok, decoded_info, _, _ = qr_detector.detectAndDecodeMulti(cv_img)
                    if ok and decoded_info:
                        for item in decoded_info:
                            if item and item.strip() and item.strip() not in pointers.qr_code_urls:
                                pointers.qr_code_urls.append(item.strip())
                except Exception as exc:
                    logger.debug("QR detection failed on PDF page %d: %s", page_idx, exc)

        pointers.raw_text = "\n".join(text_pages)

    def _extract_from_image(self, contents: bytes, pointers: ExtractedPointers):
        try:
            img_array = np.frombuffer(contents, dtype=np.uint8)
            cv_img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            if cv_img is not None:
                detector = cv2.QRCodeDetector()
                val, pts, _ = detector.detectAndDecode(cv_img)
                if val and val.strip():
                    pointers.qr_code_urls.append(val.strip())

                ok, decoded_info, _, _ = detector.detectAndDecodeMulti(cv_img)
                if ok and decoded_info:
                    for item in decoded_info:
                        if item and item.strip() and item.strip() not in pointers.qr_code_urls:
                            pointers.qr_code_urls.append(item.strip())
        except Exception as exc:
            logger.debug("Image QR detection failed: %s", exc)

    def _extract_text_pointers(self, pointers: ExtractedPointers):
        text = pointers.raw_text

        # Collapse stray spaces inside verify URL candidates before matching
        # (e.g. "coursera.org/verify/ 13MRJDMJF8TK" or "https:// coursera.org / verify / ...")
        stray_spaces_pat = re.compile(
            r"((?:https?://\s*)?(?:www\s*\.\s*)?(?:coursera\s*\.\s*org|credly\s*\.\s*com|nptel\s*\.\s*ac\s*\.\s*in|swayam\s*\.\s*gov\s*\.\s*in|udemy\s*\.\s*com)(?:\s*/\s*[A-Za-z0-9\-_]+)*(?:\s*/\s*|\s+)[A-Za-z0-9\-_]{5,40})",
            re.IGNORECASE
        )
        cleaned_text = stray_spaces_pat.sub(lambda m: re.sub(r"\s+", "", m.group(0)), text)

        # Extract verify URLs
        for m in VERIFY_URL_RE.finditer(cleaned_text):
            url = re.sub(r"\s+", "", m.group(1)).strip().rstrip(".,;)")
            if not url.startswith(("http://", "https://")):
                url = f"https://{url}"
            if url not in pointers.verify_urls:
                pointers.verify_urls.append(url)

        # Also add any QR code or hyperlink that looks like a verify URL
        for link in pointers.qr_code_urls + pointers.embedded_hyperlinks:
            clean_link = re.sub(r"\s+", "", link).strip()
            if clean_link not in pointers.verify_urls and (VERIFY_URL_RE.search(clean_link) or "coursera" in clean_link or "credly" in clean_link or "nptel" in clean_link):
                pointers.verify_urls.append(clean_link)

        # Extract credential IDs
        for m in CREDENTIAL_ID_RE.finditer(text):
            cid = m.group(1).strip()
            if cid not in pointers.credential_ids:
                pointers.credential_ids.append(cid)

        # Also extract ID from verify URLs if present
        for u in pointers.verify_urls + pointers.qr_code_urls + pointers.embedded_hyperlinks:
            id_m = re.search(r"/(?:verify|badges|records)/([A-Za-z0-9\-]{5,40})|[?&]q=([A-Za-z0-9\-]{5,40})", u)
            if id_m:
                val = id_m.group(1) or id_m.group(2)
                if val and val not in pointers.credential_ids:
                    pointers.credential_ids.append(val)

    def _extract_title(self, text: str) -> Optional[str]:
        """
        Extracts credential title from document text.
        Never falls back to filename - if extraction fails, returns None.
        Handles both course certificates and specializations.
        """
        from .matching import GENERIC_TITLES

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        for i, line in enumerate(lines):
            # 1. Pattern: "has successfully completed [Title]"
            m = re.search(
                r"(?:has\s+successfully\s+completed|successfully\s+completed|certificate\s+of\s+completion\s+in|course\s*[:\-])\s*[:\-]?\s*(.*)",
                line,
                re.IGNORECASE
            )
            if m:
                val = m.group(1).strip()
                # If the line ended right after "successfully completed", title is on the NEXT line!
                if not val and i + 1 < len(lines):
                    candidate = lines[i + 1].strip()
                    if 3 <= len(candidate) <= 80 and candidate.lower() not in GENERIC_TITLES and not candidate.lower().startswith("an online"):
                        return candidate

                # If val is boilerplate like "the online Specialization" or "an online course"
                if val.lower() in GENERIC_TITLES or val.lower().startswith("the online specialization") or val.lower().startswith("an online"):
                    if i + 1 < len(lines):
                        candidate = lines[i + 1].strip()
                        if 3 <= len(candidate) <= 80 and candidate.lower() not in GENERIC_TITLES and not candidate.lower().startswith("an online"):
                            return candidate

                # Otherwise if val is a valid title
                if len(val) >= 4 and val.lower() not in GENERIC_TITLES and not val.lower().startswith("the online"):
                    # Strip trailing boilerplate like "an online non-credit course"
                    val = re.sub(r"\s+(?:an\s+online|a\s+course|authorized\s+by).*", "", val, flags=re.IGNORECASE).strip()
                    if len(val) >= 4 and val.lower() not in GENERIC_TITLES:
                        return val[:80]

            # 2. Pattern: "Certificate of Completion" -> title on next line
            if "certificate of" in line.lower() and i + 1 < len(lines):
                candidate_line = lines[i + 1].strip()
                if 4 <= len(candidate_line) <= 80 and candidate_line.lower() not in GENERIC_TITLES and not candidate_line.lower().startswith("an online"):
                    return candidate_line

            # 3. Pattern: "[Title] an online Specialization authorized by ..."
            m_spec = re.search(r"^(.*?)\s+an\s+online\s+(?:specialization|course)\s+authorized\s+by", line, re.IGNORECASE)
            if m_spec:
                val = m_spec.group(1).strip()
                if len(val) >= 4 and val.lower() not in GENERIC_TITLES:
                    return val[:80]
                elif i > 0 and len(lines[i - 1]) >= 4 and lines[i - 1].lower() not in GENERIC_TITLES:
                    return lines[i - 1].strip()[:80]

        return None

    def _detect_skills(self, text: str) -> List[str]:
        found: List[str] = []
        lower = text.lower()
        for canonical, spec in SKILL_CATALOG.items():
            if re.search(r"\b" + re.escape(canonical.lower()) + r"\b", lower):
                if canonical not in found:
                    found.append(canonical)
                continue
            for alias in spec.aliases:
                if re.search(r"\b" + re.escape(alias.lower()) + r"\b", lower):
                    if canonical not in found:
                        found.append(canonical)
                    break
        return found
