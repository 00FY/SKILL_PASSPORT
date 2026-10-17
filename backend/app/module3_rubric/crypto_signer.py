import os
import hmac
import hashlib
import json
import logging
import secrets
from typing import Dict, Any

logger = logging.getLogger(__name__)


def _load_secret() -> bytes:
    configured = os.environ.get("SKILL_PASSPORT_HMAC_SECRET")
    if configured:
        return configured.encode("utf-8")
    # Never fall back to a key published in source code: anyone could forge passports with it.
    logger.warning(
        "SKILL_PASSPORT_HMAC_SECRET is not set; using a random per-process key. "
        "Passports signed now will stop verifying after a restart."
    )
    return secrets.token_bytes(32)


SECRET_KEY = _load_secret()

class CryptoSigner:
    """
    Computes deterministic HMAC-SHA256 tamper-proof signatures
    for passport documents, guaranteeing that neither scores, proofs, nor refusals
    have been altered, forged, or tampered with.
    """

    @staticmethod
    def _normalize(value: Any) -> Any:
        # JSON clients disagree on whole-number floats (Python writes 12.0, JavaScript writes 12),
        # so both are canonicalised to the integer form before hashing.
        if isinstance(value, float) and value.is_integer():
            return int(value)
        if isinstance(value, dict):
            return {k: CryptoSigner._normalize(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [CryptoSigner._normalize(v) for v in value]
        return value

    @staticmethod
    def _canonical_bytes(passport_payload: Dict[str, Any]) -> bytes:
        # Canonical JSON representation without the hash itself or transient audit logs
        cleaned = {k: v for k, v in passport_payload.items() if k not in ["tamper_proof_hash", "audit_log"]}
        cleaned = json.loads(json.dumps(cleaned, default=str))
        canonical_str = json.dumps(CryptoSigner._normalize(cleaned), sort_keys=True, separators=(',', ':'))
        return canonical_str.encode('utf-8')

    @staticmethod
    def sign_passport(passport_payload: Dict[str, Any]) -> str:
        canonical_bytes = CryptoSigner._canonical_bytes(passport_payload)
        sig = hmac.new(SECRET_KEY, canonical_bytes, hashlib.sha256).hexdigest()
        return f"hmac-sha256:{sig}"

    @staticmethod
    def verify_passport_signature(passport_payload: Dict[str, Any], signature: str) -> Dict[str, Any]:
        """
        Verifies the cryptographic signature of a passport payload.
        Returns a structured dictionary: { 'valid': bool, 'reason': str }.
        """
        if not signature:
            return {
                "valid": False,
                "reason": "Missing signature: Document contains no cryptographic seal."
            }

        canonical_bytes = CryptoSigner._canonical_bytes(passport_payload)
        expected_hmac = f"hmac-sha256:{hmac.new(SECRET_KEY, canonical_bytes, hashlib.sha256).hexdigest()}"

        if hmac.compare_digest(expected_hmac, signature):
            return {
                "valid": True,
                "reason": "Cryptographic HMAC-SHA256 signature successfully verified against canonical passport JSON."
            }

        # Unkeyed "sha256:" digests are deliberately not accepted: anyone can recompute them.
        return {
            "valid": False,
            "reason": "Signature verification failed: Passport payload has been altered, forged, or tampered with."
        }

    @staticmethod
    def verify_passport(passport_payload: Dict[str, Any], claimed_hash: str) -> bool:
        return CryptoSigner.verify_passport_signature(passport_payload, claimed_hash)["valid"]
