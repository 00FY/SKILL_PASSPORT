import logging
from typing import Optional

from ..schemas import CertificateEvidence
from .cert_verifier import CertificateVerifierService

logger = logging.getLogger(__name__)


class CertificateParser:
    """
    Forensic credential parser & issuer verification client.
    Extracts verification pointers (printed URLs, hyperlinks, QR codes)
    and queries the issuer's record directly against a strict host allowlist.
    """

    def __init__(self):
        self.verifier = CertificateVerifierService()

    def parse_file(
        self,
        filename: str,
        contents: bytes,
        candidate_name: Optional[str] = None
    ) -> CertificateEvidence:
        return self.verifier.verify(filename, contents, candidate_name)
