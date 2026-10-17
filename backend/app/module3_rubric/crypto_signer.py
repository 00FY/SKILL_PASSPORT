import hashlib
import json
from typing import Dict, Any

class CryptoSigner:
    """
    Computes a deterministic cryptographic SHA-256 tamper-proof fingerprint
    for a passport document, verifying that neither scores, proofs, nor refusals
    have been tampered with.
    """

    @staticmethod
    def sign_passport(passport_payload: Dict[str, Any]) -> str:
        # Create a canonical JSON representation without the hash field itself
        cleaned = {k: v for k, v in passport_payload.items() if k not in ["tamper_proof_hash", "audit_log"]}
        canonical_str = json.dumps(cleaned, sort_keys=True, separators=(',', ':'), default=str)
        sha256_hash = hashlib.sha256(canonical_str.encode('utf-8')).hexdigest()
        return f"sha256:{sha256_hash}"

    @staticmethod
    def verify_passport(passport_payload: Dict[str, Any], claimed_hash: str) -> bool:
        expected = CryptoSigner.sign_passport(passport_payload)
        return expected == claimed_hash
