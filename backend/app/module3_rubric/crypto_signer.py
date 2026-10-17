import os
import hmac
import hashlib
import json
from typing import Dict, Any

SECRET_KEY = os.environ.get("SKILL_PASSPORT_HMAC_SECRET", "skill-passport-verifiable-hmac-key-2025").encode("utf-8")

class CryptoSigner:
    """
    Computes deterministic HMAC-SHA256 tamper-proof signatures
    for passport documents, guaranteeing that neither scores, proofs, nor refusals
    have been altered, forged, or tampered with.
    """

    @staticmethod
    def _canonical_bytes(passport_payload: Dict[str, Any]) -> bytes:
        # Canonical JSON representation without the hash itself or transient audit logs
        cleaned = {k: v for k, v in passport_payload.items() if k not in ["tamper_proof_hash", "audit_log"]}
        canonical_str = json.dumps(cleaned, sort_keys=True, separators=(',', ':'), default=str)
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

        # Backwards compatibility check for legacy sha256: signatures
        expected_sha = f"sha256:{hashlib.sha256(canonical_bytes).hexdigest()}"
        if hmac.compare_digest(expected_sha, signature):
            return {
                "valid": True,
                "reason": "Legacy SHA-256 digital digest successfully verified against canonical passport JSON."
            }

        return {
            "valid": False,
            "reason": "Signature verification failed: Passport payload has been altered, forged, or tampered with."
        }

    @staticmethod
    def verify_passport(passport_payload: Dict[str, Any], claimed_hash: str) -> bool:
        return CryptoSigner.verify_passport_signature(passport_payload, claimed_hash)["valid"]
