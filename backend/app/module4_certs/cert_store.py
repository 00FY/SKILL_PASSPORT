"""
Server-side record of certificates this server checked.

/api/upload-cert stores each verification result here, and an analysis uses only certificates found here
(by id). Whatever else a client sends about a certificate (issuer, status, skills) is ignored, so a passport
can't carry a certificate the server never saw, or a status it never gave. In memory: cleared on restart.
"""
import threading
import time
from typing import Dict, Iterable, List, Optional, Tuple

from ..schemas import CertificateEvidence
from .matching import name_match

CERT_TTL_S = 24 * 3600
MAX_CERTS = 5000
VERIFIED_STATUSES = ("verified", "issuer_verified")


class CertificateStore:
    def __init__(self, ttl_s: float = CERT_TTL_S):
        self.ttl_s = ttl_s
        self._certs: Dict[str, Tuple[float, CertificateEvidence]] = {}
        self._lock = threading.Lock()

    def put(self, cert: CertificateEvidence) -> None:
        with self._lock:
            self._purge()
            if len(self._certs) >= MAX_CERTS:
                oldest = min(self._certs, key=lambda k: self._certs[k][0])
                del self._certs[oldest]
            self._certs[cert.id] = (time.time(), cert.model_copy(deep=True))

    def resolve(self, ids: Iterable[str]) -> Tuple[List[CertificateEvidence], List[str]]:
        """Returns (the stored certificates for these ids, ids that aren't known here)."""
        found, unknown = [], []
        with self._lock:
            self._purge()
            for cert_id in ids:
                entry = self._certs.get(cert_id)
                if entry:
                    found.append(entry[1].model_copy(deep=True))
                else:
                    unknown.append(cert_id)
        return found, unknown

    def _purge(self) -> None:
        cutoff = time.time() - self.ttl_s
        for key in [k for k, (t, _) in self._certs.items() if t < cutoff]:
            del self._certs[key]


def check_holder(cert: CertificateEvidence, holder_name: Optional[str]) -> CertificateEvidence:
    """
    An issuer-verified certificate counts only for the person it was issued to. If the issuer's record
    names someone else, it's marked as a mismatch; if the holder's name isn't known, it can't be confirmed.
    """
    if cert.issuer_status not in VERIFIED_STATUSES:
        return cert
    recipient = (cert.issuer_record or {}).get("recipient_name") or cert.candidate_name
    if not recipient:
        return cert
    if holder_name and name_match(recipient, holder_name):
        return cert
    if holder_name:
        cert.issuer_status = "unverified"
        cert.mismatch_reason = (f"Official issuer record lists a different recipient ('{recipient}') "
                                f"than the passport holder ('{holder_name}')")
        cert.confidence_score = 0.0
        cert.score_tier = 0
    else:
        cert.issuer_status = "pending"
        cert.mismatch_reason = (f"The issuer confirms this certificate for '{recipient}'; add the candidate's name "
                                "to confirm it's theirs")
        cert.score_tier = 50
    return cert
