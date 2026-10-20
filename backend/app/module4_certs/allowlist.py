import ipaddress
import logging
from urllib.parse import urlparse, urljoin
from typing import Tuple, Optional
import httpx

logger = logging.getLogger(__name__)

# Exact root domains permitted for verification
ALLOWED_ISSUER_DOMAINS = {
    "coursera.org",
    "credly.com",
    "nptel.ac.in",
    "swayam.gov.in",
    "udemy.com",
}

MAX_REDIRECTS = 3
MAX_RESPONSE_BYTES = 2 * 1024 * 1024  # 2 MB limit
REQUEST_TIMEOUT_S = 8.0
USER_AGENT = "SkillPassport-CertificateVerifier/1.0 (+https://github.com/00FY/SKILL_PASSPORT)"


def is_allowed_domain(hostname: Optional[str]) -> bool:
    """
    Validates whether a hostname belongs to an allowed issuer.
    Strictly prevents lookalikes like 'coursera-verify.com' or 'fake-credly.com'.
    """
    if not hostname:
        return False
    host = hostname.lower().strip().rstrip(".")

    # Reject IP addresses directly
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        pass

    # Reject localhost or internal names
    if host in ("localhost", "local", "internal", "intranet"):
        return False

    for allowed in ALLOWED_ISSUER_DOMAINS:
        if host == allowed or host.endswith("." + allowed):
            return True

    return False


def validate_issuer_url(url: str) -> Tuple[bool, Optional[str]]:
    """
    Validates that a URL is HTTPS and belongs to an allowed issuer domain.
    Returns (is_valid, error_reason).
    """
    if not url or not isinstance(url, str):
        return False, "Empty or non-string URL"

    try:
        parsed = urlparse(url.strip())
    except Exception as exc:
        return False, f"Malformed URL: {exc}"

    if parsed.scheme.lower() != "https":
        return False, f"Insecure scheme '{parsed.scheme}': only https is permitted"

    if parsed.username or parsed.password:
        return False, "Credentials in URL are disallowed"

    if parsed.port and parsed.port not in (443,):
        return False, f"Disallowed port: {parsed.port}"

    if not is_allowed_domain(parsed.hostname):
        return False, f"Host '{parsed.hostname}' is not on the trusted issuer allowlist"

    return True, None


def safe_fetch_issuer_page(url: str) -> Tuple[int, bytes, str, str]:
    """
    Safely fetches an issuer page with:
    - Host allowlist enforcement on every redirect
    - Max response size cap
    - Short timeout
    - No SSRF to internal/private hosts
    Returns: (status_code, raw_bytes, text, final_url)
    Raises: ValueError on security violation, httpx.HTTPError on network failure
    """
    valid, reason = validate_issuer_url(url)
    if not valid:
        raise ValueError(f"URL security violation: {reason}")

    current_url = url
    redirect_count = 0

    with httpx.Client(
        timeout=REQUEST_TIMEOUT_S,
        follow_redirects=False,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8"}
    ) as client:
        while True:
            resp = client.get(current_url)

            # Check response size cap
            content = resp.content
            if len(content) > MAX_RESPONSE_BYTES:
                raise ValueError(f"Response size {len(content)} exceeds cap of {MAX_RESPONSE_BYTES} bytes")

            if resp.is_redirect and "location" in resp.headers:
                redirect_count += 1
                if redirect_count > MAX_REDIRECTS:
                    raise ValueError(f"Too many redirects ({redirect_count})")

                next_url = urljoin(current_url, resp.headers["location"])
                next_valid, next_reason = validate_issuer_url(next_url)
                if not next_valid:
                    raise ValueError(f"Redirect to disallowed URL rejected: {next_reason} ({next_url})")

                current_url = next_url
                continue

            return resp.status_code, content, resp.text, current_url
