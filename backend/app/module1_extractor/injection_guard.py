import re
import base64
import binascii
import unicodedata
from typing import Tuple, List
from ..schemas import SecurityFlag

# Common zero-width and invisible unicode characters used in steganography / prompt attacks
ZERO_WIDTH_CHARS = [
    '​',  # zero width space
    '‌',  # zero width non-joiner
    '‍',  # zero width joiner
    '﻿',  # zero width no-break space (BOM)
    '⁠',  # word joiner
    '‎',  # LTR mark
    '‏',  # RTL mark
    '­',  # soft hyphen
]

_PRIOR = r"(previous|prior|above|earlier|preceding|all)"
_RULES = r"(instructions?|rules|prompts?|directions|guidelines|context)"

# Prompt injection heuristic patterns (matched after NFKC normalisation)
INJECTION_PATTERNS = [
    (rf"(?i)ignore\s+(all\s+)?{_PRIOR}\s+(the\s+)?{_RULES}", "STEGANOGRAPHY_OR_INJECTION", "CRITICAL"),
    (rf"(?i)(disregard|forget|override|bypass)\s+(all\s+)?({_PRIOR}\s+)?(the\s+|your\s+)?{_RULES}", "STEGANOGRAPHY_OR_INJECTION", "CRITICAL"),
    (r"(?i)system\s*(override)?\s*:\s*(please\s+)?mark\s+(all\s+)?(skills?|claims?)\s+(as\s+)?verified", "STEGANOGRAPHY_OR_INJECTION", "CRITICAL"),
    (r"(?i)mark\s+(all\s+|every\s+)(skills?|claims?)\s+(as\s+)?verified", "SCORE_MANIPULATION", "HIGH"),
    (r"(?i)(give|assign|award|rate)\s+(this\s+)?(candidate|applicant|me)\s+(a\s+|an\s+)?(100\s*%|full\s+marks?|10\s*/\s*10|perfect\s+score|top\s+score|maximum\s+score)", "SCORE_MANIPULATION", "HIGH"),
    (r"(?i)you\s+are\s+now\s+(in\s+)?(admin|root|debug|jailbreak|developer|dan)\s+mode", "STEGANOGRAPHY_OR_INJECTION", "CRITICAL"),
    (r"(?i)assistant\s*:\s*verified", "DIRECT_OUTPUT_FORGERY", "HIGH"),
    (r"(?i)do\s+not\s+(verify|check|audit|blame|run\s+tests\s+on)\s+(this|my|the)\s+(candidate|resume|repo|repository|claims?)", "VERIFIER_BYPASS", "MEDIUM"),
    (r"(?i)override\s+evaluation\s+criteria", "STEGANOGRAPHY_OR_INJECTION", "CRITICAL"),
    (r"(?i)note\s+to\s+(the\s+)?(ai|llm|gpt|chatgpt|assistant|language\s+model|screener|ats|automated\s+reviewer)", "STEGANOGRAPHY_OR_INJECTION", "HIGH"),
    (r"(?is)<\s*system\s*>.*?<\s*/\s*system\s*>", "STEGANOGRAPHY_OR_INJECTION", "CRITICAL"),
    (r"(?is)\[system_instruction\].*?\[/system_instruction\]", "STEGANOGRAPHY_OR_INJECTION", "CRITICAL"),
]

# Hidden-text markers. Only checked inside style declarations, so ordinary prose such as
# "dark mode with white text" is not mistaken for camouflage.
HIDDEN_STYLE_PATTERNS = [
    (r"(?i)\bcolor\s*:\s*(#ffffff|#fff\b|white|rgb\(\s*255\s*,\s*255\s*,\s*255\s*\)|rgba\([^)]*,\s*0(\.0+)?\s*\))", "WHITE_ON_WHITE_TEXT"),
    (r"(?i)font-size\s*:\s*([0-1](\.\d+)?\s*(pt|px)|0\b)", "MICRO_FONT_STEGANOGRAPHY"),
    (r"(?i)(display\s*:\s*none|visibility\s*:\s*hidden|opacity\s*:\s*0(\.0+)?\b)", "CSS_HIDDEN_PAYLOAD"),
]

STYLE_CONTEXT_PATTERNS = [
    r"""(?is)style\s*=\s*(["'])(?P<css>.*?)\1""",
    r"""(?is)<\s*style[^>]*>(?P<css>.*?)<\s*/\s*style\s*>""",
]

BASE64_KEYWORDS = [
    "ignore previous", "ignore all", "disregard", "system:", "system override",
    "mark all skills", "jailbreak", "admin mode", "root mode", "100%",
    "score: 100", "eval criteria", "full marks", "perfect score",
]


def _looks_like_text(decoded: str) -> bool:
    if not decoded:
        return False
    printable = sum(1 for ch in decoded if ch.isprintable() or ch in "\n\t")
    return printable / len(decoded) > 0.9


class PromptInjectionDefense:
    """
    Sanitizes resume text and defends against prompt injections,
    invisible zero-width unicode steganography, micro-font attacks,
    white-text camouflage, and base64-encoded command overrides.
    """

    def sanitize(self, raw_text: str) -> Tuple[str, List[SecurityFlag]]:
        flags: List[SecurityFlag] = []

        # 1. Detect and strip zero-width characters (​, ‌, ‍, ﻿, etc.)
        cleaned_text = raw_text
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

        # Fold look-alike characters (full-width letters, ligatures) so patterns can't be dodged with them
        cleaned_text = unicodedata.normalize("NFKC", cleaned_text)

        # 2. Check style declarations for hidden text / CSS camouflage tricks (#FFFFFF, font-size < 2pt)
        for ctx_pattern in STYLE_CONTEXT_PATTERNS:
            for m in list(re.finditer(ctx_pattern, cleaned_text)):
                css = m.group("css")
                hits = [(flag_type, hm.group(0)) for pattern, flag_type in HIDDEN_STYLE_PATTERNS for hm in [re.search(pattern, css)] if hm]
                if not hits:
                    continue
                for flag_type, snippet in hits:
                    flags.append(
                        SecurityFlag(
                            flag_type="STEGANOGRAPHY_OR_INJECTION",
                            severity="CRITICAL",
                            raw_payload_snippet=f"Detected hidden font/color camouflage ({flag_type}): {snippet}",
                            action_taken="Quarantined hidden text and sanitized inline styling tags."
                        )
                    )
                cleaned_text = cleaned_text.replace(m.group(0), " [SANITIZED_HIDDEN_TAG] ")

        # 3. Detect Base64-encoded override strings
        b64_pattern = r'[A-Za-z0-9+/]{16,}={0,2}'
        for match in re.finditer(b64_pattern, cleaned_text):
            candidate = match.group(0)
            try:
                padded = candidate + "=" * (-len(candidate) % 4)
                decoded = base64.b64decode(padded, validate=True).decode('utf-8')
            except (binascii.Error, ValueError, UnicodeDecodeError):
                continue
            if not _looks_like_text(decoded):
                continue
            lower_dec = decoded.lower()
            if any(kw in lower_dec for kw in BASE64_KEYWORDS):
                flags.append(
                    SecurityFlag(
                        flag_type="STEGANOGRAPHY_OR_INJECTION",
                        severity="CRITICAL",
                        raw_payload_snippet=f"Base64 Encoded Injection Payload: '{candidate[:32]}...' -> Decoded: '{decoded.strip()[:60]}...'",
                        action_taken="Decoded and neutralized hidden Base64 adversarial instructions."
                    )
                )
                cleaned_text = cleaned_text.replace(candidate, " [SANITIZED_BASE64_INJECTION] ")

        # 4. Check for adversarial prompt injection sentences
        for pattern, flag_type, severity in INJECTION_PATTERNS:
            for m in list(re.finditer(pattern, cleaned_text)):
                matched_snippet = m.group(0)
                if matched_snippet not in cleaned_text:
                    continue
                flags.append(
                    SecurityFlag(
                        flag_type=flag_type,
                        severity=severity,
                        raw_payload_snippet=matched_snippet[:200],
                        action_taken="Adversarial command quarantined and neutralized before LLM prompt assembly."
                    )
                )
                cleaned_text = cleaned_text.replace(matched_snippet, f" [FLAGGED_ATTACK: {flag_type}] ")

        return cleaned_text, flags
