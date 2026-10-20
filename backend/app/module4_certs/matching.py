import re
import unicodedata
from typing import Optional, List, Set

HONORIFICS = {"mr", "ms", "mrs", "dr", "prof", "shri", "smt"}

GENERIC_TITLES = {
    "skills",
    "skill",
    "certificate",
    "certificates",
    "completion",
    "course",
    "courses",
    "specialization",
    "specializations",
    "verified certificate",
    "online course",
    "the online specialization",
    "online specialization",
    "statement of accomplishment",
    "accomplishment",
    "accomplishments",
    "certificate of completion",
}


def normalize_text(text: Optional[str]) -> str:
    """
    Normalizes text by stripping accents/diacritics, lowercasing, and collapsing whitespace.
    """
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", text)
    no_accents = "".join(c for c in nfkd if not unicodedata.combining(c))
    collapsed = re.sub(r"\s+", " ", no_accents.lower()).strip()
    return collapsed


def fuzzy_contains(text: Optional[str], target: Optional[str], threshold: float = 0.85) -> bool:
    """
    Fuzzy containment test: Checks if target string appears inside text.
    1. Exact normalized substring test
    2. Normalized token-based overlap test (~0.85 threshold)
    """
    if not text or not target:
        return False

    norm_text = normalize_text(text)
    norm_target = normalize_text(target)

    if not norm_target:
        return False

    # 1. Exact normalized substring
    if norm_target in norm_text:
        return True

    # 2. Token-based containment
    clean_text = re.sub(r"[^\w\s]", " ", norm_text)
    text_tokens = set(clean_text.split())

    clean_target = re.sub(r"[^\w\s]", " ", norm_target)
    target_tokens = [t for t in clean_target.split() if len(t) > 1 and t not in HONORIFICS]

    if not target_tokens:
        return False

    # All or high-percentage of target tokens appear in document text
    matching_tokens = sum(1 for t in target_tokens if t in text_tokens)
    ratio = matching_tokens / len(target_tokens)
    if ratio >= threshold or (len(target_tokens) <= 3 and matching_tokens == len(target_tokens)):
        return True

    return False


def fuzzy_eq(a: Optional[str], b: Optional[str]) -> bool:
    """Fuzzy equality between two names."""
    return name_match(a, b)


def _clean_tokens(name: Optional[str]) -> List[str]:
    if not name:
        return []
    cleaned = re.sub(r"[^\w\s]", " ", name.lower())
    tokens = [t.strip() for t in cleaned.split() if t.strip()]
    return [t for t in tokens if t not in HONORIFICS]


def name_match(record_name: Optional[str], target_name: Optional[str]) -> bool:
    """
    Compares recipient name on issuer record with candidate name or extracted name.
    Supports:
    - Exact match (case/space-insensitive)
    - Initials (e.g. 'Priya S.' matches 'Priya Sharma', 'A. R. Smith' matches 'Alex R. Smith')
    - Name subsets (e.g. 'Priya Sharma' matches 'Priya')
    - Permuted order (e.g. 'Smith, Jane' matches 'Jane Smith')
    """
    if not record_name or not target_name:
        return False

    r_raw = record_name.strip().lower()
    t_raw = target_name.strip().lower()

    if r_raw == t_raw:
        return True

    r_tokens = _clean_tokens(record_name)
    t_tokens = _clean_tokens(target_name)

    if not r_tokens or not t_tokens:
        return False

    # Check if one is a direct substring of the other (if at least 3 chars)
    if len(r_raw) >= 3 and len(t_raw) >= 3:
        if r_raw in t_raw or t_raw in r_raw:
            return True

    # Check set equality or permutation
    r_set = set(r_tokens)
    t_set = set(t_tokens)
    if r_set == t_set:
        return True

    # Check token overlap
    common = r_set.intersection(t_set)
    min_tokens = min(len(r_tokens), len(t_tokens))

    # If all tokens of the shorter name are present in the longer name
    if r_set.issubset(t_set) or t_set.issubset(r_set):
        return True

    # Initials matching:
    # Compare first name and check if remaining initials align
    if r_tokens[0] == t_tokens[0]:
        # First names match
        if len(r_tokens) == 1 or len(t_tokens) == 1:
            return True

        # Check last names or initials
        r_rem = r_tokens[1:]
        t_rem = t_tokens[1:]

        # If any remaining token in r is an initial prefix of remaining token in t or vice versa
        for r_tok in r_rem:
            for t_tok in t_rem:
                if r_tok == t_tok or (len(r_tok) == 1 and t_tok.startswith(r_tok)) or (len(t_tok) == 1 and r_tok.startswith(t_tok)):
                    return True

    # If at least 2 tokens match for longer names
    if len(common) >= 2:
        return True

    return False


def title_match(record_title: Optional[str], target_title: Optional[str]) -> bool:
    """
    Compares credential title on issuer record with certificate title or skills.
    Checks for high word-set overlap or substring inclusion.
    """
    if not record_title or not target_title:
        return True  # If one title is not extracted, don't fail solely on missing title

    r_raw = record_title.strip().lower()
    t_raw = target_title.strip().lower()

    if r_raw == t_raw:
        return True

    # Substring check
    if len(r_raw) >= 4 and len(t_raw) >= 4:
        if r_raw in t_raw or t_raw in r_raw:
            return True

    # Token overlap check
    STOP_WORDS = {"certificate", "completion", "specialization", "course", "certified", "the", "in", "of", "and", "&", "for", "with"}
    r_tokens = {t for t in re.sub(r"[^\w\s]", " ", r_raw).split() if len(t) > 2 and t not in STOP_WORDS}
    t_tokens = {t for t in re.sub(r"[^\w\s]", " ", t_raw).split() if len(t) > 2 and t not in STOP_WORDS}

    if not r_tokens or not t_tokens:
        return True

    overlap = r_tokens.intersection(t_tokens)
    if overlap:
        # If at least 40% of tokens in the shorter title match
        ratio = len(overlap) / min(len(r_tokens), len(t_tokens))
        if ratio >= 0.4:
            return True

    return False
