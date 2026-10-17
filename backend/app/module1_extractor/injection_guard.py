import re
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
    (r"(?i)ignore\s+(all\s+)?(previous|prior|above)\s+(instructions|rules|prompts|directions)", "OVERRIDE_INSTRUCTION", "CRITICAL"),
    (r"(?i)system\s*:\s*mark\s+(all\s+)?skills?\s+(as\s+)?verified", "SYSTEM_PROMPT_HIJACK", "CRITICAL"),
    (r"(?i)give\s+(this\s+)?candidate\s+(a\s+)?(100%|full\s+marks?|10\/10|perfect\s+score)", "SCORE_MANIPULATION", "HIGH"),
    (r"(?i)you\s+are\s+now\s+(in\s+)?(admin|root|debug|jailbreak|developer)\s+mode", "ROLEPLAY_JAILBREAK", "CRITICAL"),
    (r"(?i)assistant\s*:\s*verified", "DIRECT_OUTPUT_FORGERY", "HIGH"),
    (r"(?i)do\s+not\s+(verify|check|audit|blame|run\s+tests)", "VERIFIER_BYPASS", "MEDIUM"),
    (r"(?i)override\s+evaluation\s+criteria", "EVAL_CRITERIA_OVERRIDE", "CRITICAL"),
    (r"(?i)<\s*system\s*>.*?<\s*/\s*system\s*>", "XML_SYSTEM_TAG_INJECTION", "CRITICAL"),
    (r"(?i)\[system_instruction\].*?\[/system_instruction\]", "BRACKETED_SYSTEM_INJECTION", "CRITICAL"),
]

# Hidden text markers (e.g., color: #fff, display: none, font-size: 0px)
HIDDEN_TEXT_PATTERNS = [
    (r"(?i)(color\s*:\s*(#ffffff|white|rgba\(\s*255\s*,\s*255\s*,\s*255\s*,\s*0(\.0+)?\s*\)))", "WHITE_ON_WHITE_TEXT"),
    (r"(?i)(display\s*:\s*none|opacity\s*:\s*0|font-size\s*:\s*0(px)?)", "CSS_HIDDEN_PAYLOAD"),
]

class PromptInjectionDefense:
    """
    Sanitizes resume text and defends against prompt injections,
    invisible zero-width unicode steganography, and hidden text exploits.
    """

    def sanitize(self, raw_text: str) -> Tuple[str, List[SecurityFlag]]:
        flags: List[SecurityFlag] = []
        cleaned_text = raw_text

        # 1. Detect and strip zero-width characters
        zw_found = 0
        for zw in ZERO_WIDTH_CHARS:
            if zw in cleaned_text:
                zw_found += cleaned_text.count(zw)
                cleaned_text = cleaned_text.replace(zw, "")

        if zw_found > 0:
            flags.append(
                SecurityFlag(
                    flag_type="ZERO_WIDTH_STEGANOGRAPHY",
                    severity="HIGH",
                    raw_payload_snippet=f"Detected {zw_found} invisible zero-width characters designed to bypass tokenizers.",
                    action_taken="Purged all zero-width unicode artifacts from text stream."
                )
            )

        # 2. Check for hidden text / CSS camouflage tricks
        for pattern, flag_type in HIDDEN_TEXT_PATTERNS:
            matches = list(re.finditer(pattern, cleaned_text))
            if matches:
                snippets = [m.group(0) for m in matches[:3]]
                flags.append(
                    SecurityFlag(
                        flag_type=flag_type,
                        severity="MEDIUM",
                        raw_payload_snippet=f"Found suspicious hidden style markers: {', '.join(snippets)}",
                        action_taken="Flagged for manual audit; sanitized inline styling markers."
                    )
                )
                cleaned_text = re.sub(pattern, " [SANITIZED_HIDDEN_TAG] ", cleaned_text)

        # 3. Check for adversarial prompt injection sentences
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
