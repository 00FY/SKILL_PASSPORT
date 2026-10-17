import re
import base64
from typing import Tuple, List
from ..schemas import SecurityFlag

# Common zero-width and invisible unicode characters used in steganography / prompt attacks
ZERO_WIDTH_CHARS = [
    '\u200b',  # zero width space
    '\u200c',  # zero width non-joiner
    '\u200d',  # zero width joiner
    '\ufeff',  # zero width no-break space (BOM)
    '\u2060',  # word joiner
    '\u200e',  # LTR mark
    '\u200f',  # RTL mark
]

# Prompt injection heuristic patterns
INJECTION_PATTERNS = [
    (r"(?i)ignore\s+(all\s+)?(previous|prior|above)\s+(instructions|rules|prompts|directions)", "STEGANOGRAPHY_OR_INJECTION", "CRITICAL"),
    (r"(?i)system\s*:\s*mark\s+(all\s+)?skills?\s+(as\s+)?verified", "STEGANOGRAPHY_OR_INJECTION", "CRITICAL"),
    (r"(?i)give\s+(this\s+)?candidate\s+(a\s+)?(100%|full\s+marks?|10\/10|perfect\s+score)", "SCORE_MANIPULATION", "HIGH"),
    (r"(?i)you\s+are\s+now\s+(in\s+)?(admin|root|debug|jailbreak|developer)\s+mode", "STEGANOGRAPHY_OR_INJECTION", "CRITICAL"),
    (r"(?i)assistant\s*:\s*verified", "DIRECT_OUTPUT_FORGERY", "HIGH"),
    (r"(?i)do\s+not\s+(verify|check|audit|blame|run\s+tests)", "VERIFIER_BYPASS", "MEDIUM"),
    (r"(?i)override\s+evaluation\s+criteria", "STEGANOGRAPHY_OR_INJECTION", "CRITICAL"),
    (r"(?i)<\s*system\s*>.*?<\s*/\s*system\s*>", "STEGANOGRAPHY_OR_INJECTION", "CRITICAL"),
    (r"(?i)\[system_instruction\].*?\[/system_instruction\]", "STEGANOGRAPHY_OR_INJECTION", "CRITICAL"),
]

# Hidden text markers (white text #FFFFFF, font size < 2pt, display: none, opacity: 0)
HIDDEN_TEXT_PATTERNS = [
    (r"(?i)(color\s*:\s*(#ffffff|#fff|white|rgb\(\s*255\s*,\s*255\s*,\s*255\s*\)|rgba\(\s*255\s*,\s*255\s*,\s*255\s*,\s*0(\.0+)?\s*\)))", "WHITE_ON_WHITE_TEXT"),
    (r"(?i)(font-size\s*:\s*([0-1](\.\d+)?(pt|px)|0\b))", "MICRO_FONT_STEGANOGRAPHY"),
    (r"(?i)(display\s*:\s*none|visibility\s*:\s*hidden|opacity\s*:\s*0)", "CSS_HIDDEN_PAYLOAD"),
]

class PromptInjectionDefense:
    """
    Sanitizes resume text and defends against prompt injections,
    invisible zero-width unicode steganography, micro-font attacks,
    white-text camouflage, and base64-encoded command overrides.
    """

    def sanitize(self, raw_text: str) -> Tuple[str, List[SecurityFlag]]:
        flags: List[SecurityFlag] = []
        cleaned_text = raw_text

        # 1. Detect and strip zero-width characters (\u200b, \u200c, \u200d, \ufeff, etc.)
        zw_found = 0
        for zw in ZERO_WIDTH_CHARS:
            if zw in cleaned_text:
                zw_found += cleaned_text.count(zw)
                cleaned_text = cleaned_text.replace(zw, "")

        if zw_found > 0:
            flags.append(
                SecurityFlag(
                    flag_type="STEGANOGRAPHY_OR_INJECTION",
                    severity="CRITICAL",
                    raw_payload_snippet=f"Detected {zw_found} invisible zero-width characters (\\u200b, \\u200c, \\u200d, \\ufeff) embedded in text stream.",
                    action_taken="Purged all zero-width unicode artifacts from text stream."
                )
            )

        # 2. Check for hidden text / CSS camouflage tricks (#FFFFFF, font-size < 2pt)
        for pattern, flag_type in HIDDEN_TEXT_PATTERNS:
            matches = list(re.finditer(pattern, cleaned_text))
            if matches:
                snippets = [m.group(0) for m in matches[:3]]
                flags.append(
                    SecurityFlag(
                        flag_type="STEGANOGRAPHY_OR_INJECTION",
                        severity="CRITICAL",
                        raw_payload_snippet=f"Detected hidden font/color camouflage ({flag_type}): {', '.join(snippets)}",
                        action_taken="Quarantined hidden text and sanitized inline styling tags."
                    )
                )
                cleaned_text = re.sub(pattern, " [SANITIZED_HIDDEN_TAG] ", cleaned_text)

        # 3. Detect Base64-encoded override strings
        b64_pattern = r'[A-Za-z0-9+/]{16,}={0,2}'
        for match in re.finditer(b64_pattern, cleaned_text):
            candidate = match.group(0)
            try:
                decoded = base64.b64decode(candidate).decode('utf-8', errors='ignore')
                lower_dec = decoded.lower()
                injection_keywords = [
                    "ignore previous", "ignore all", "system:", "system override",
                    "mark all skills", "verified", "jailbreak", "admin mode",
                    "100%", "root mode", "score: 100", "eval criteria"
                ]
                if any(kw in lower_dec for kw in injection_keywords):
                    flags.append(
                        SecurityFlag(
                            flag_type="STEGANOGRAPHY_OR_INJECTION",
                            severity="CRITICAL",
                            raw_payload_snippet=f"Base64 Encoded Injection Payload: '{candidate[:32]}...' -> Decoded: '{decoded.strip()[:60]}...'",
                            action_taken="Decoded and neutralized hidden Base64 adversarial instructions."
                        )
                    )
                    cleaned_text = cleaned_text.replace(candidate, " [SANITIZED_BASE64_INJECTION] ")
            except Exception:
                pass

        # 4. Check for adversarial prompt injection sentences
        for pattern, flag_type, severity in INJECTION_PATTERNS:
            matches = list(re.finditer(pattern, cleaned_text))
            for m in matches:
                matched_snippet = m.group(0)
                flags.append(
                    SecurityFlag(
                        flag_type=flag_type,
                        severity=severity,
                        raw_payload_snippet=matched_snippet,
                        action_taken="Adversarial command quarantined and neutralized before LLM prompt assembly."
                    )
                )
                # Neutralize snippet in text
                cleaned_text = cleaned_text.replace(matched_snippet, f" [FLAGGED_ATTACK: {flag_type}] ")

        return cleaned_text, flags
