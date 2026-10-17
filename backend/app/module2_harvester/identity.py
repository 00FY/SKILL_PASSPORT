import re
from typing import Iterable, List, Optional

NOREPLY_SUFFIX = "@users.noreply.github.com"


def _normalize_name(name: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[.,]", " ", (name or "").lower())).strip()


class IdentityMatcher:
    """
    Decides whether a git author belongs to the candidate.

    Identities can be emails ("soham@gmail.com"), usernames / GitHub logins ("sohamk234")
    or full names ("Soham Kadam"). Matching is exact per identity kind, never a substring
    search, so a short name like "Al" can't claim lines written by "Alex".
    """

    def __init__(self, identities: Optional[Iterable[str]] = None, candidate_name: Optional[str] = None):
        self.emails = set()
        self.logins = set()
        self.names = set()
        for raw in identities or []:
            ident = (raw or "").strip()
            if not ident:
                continue
            if "@" in ident and not ident.startswith("@"):
                self.emails.add(ident.lower())
            elif " " in ident:
                self.names.add(_normalize_name(ident))
            else:
                self.logins.add(ident.lstrip("@").lower())
        if candidate_name and candidate_name.strip() and candidate_name.strip().lower() != "candidate":
            normalized = _normalize_name(candidate_name)
            if " " in normalized:
                self.names.add(normalized)
            else:
                self.logins.add(normalized)

    @property
    def is_empty(self) -> bool:
        return not (self.emails or self.logins or self.names)

    def describe(self) -> List[str]:
        return sorted(self.emails) + sorted(self.logins) + sorted(self.names)

    def matches(self, author_name: str, author_email: str) -> bool:
        email = (author_email or "").strip().lower()
        name = _normalize_name(author_name)

        if email and email in self.emails:
            return True

        local = email.split("@")[0] if email else ""
        if email.endswith(NOREPLY_SUFFIX):
            # 12345+login@users.noreply.github.com
            local = local.split("+")[-1]
        if local and local in self.logins:
            return True
        if name and (name in self.logins or name.replace(" ", "") in self.logins):
            return True
        if name and name in self.names:
            return True

        author_tokens = name.split()
        for full_name in self.names:
            tokens = full_name.split()
            if len(tokens) < 2 or not author_tokens:
                continue
            # First name must match exactly; remaining tokens may be initials ("Priya S." ~ "Priya Sharma")
            if tokens[0] != author_tokens[0]:
                continue
            rest = author_tokens[1:]
            if all(any(a == t or (len(t) == 1 and a.startswith(t)) for a in rest) for t in tokens[1:]):
                return True
        return False
