import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

NAME_PATTERN = re.compile(r"^[A-Za-z0-9_.\-]{1,100}$")


class RepoSourceError(ValueError):
    """The repository reference itself is invalid or not allowed (bad input)."""


class RepoAccessError(RuntimeError):
    """The repository reference is valid but could not be fetched or analysed."""


def allowed_hosts():
    raw = os.getenv("SKILL_PASSPORT_ALLOWED_GIT_HOSTS", "github.com,gitlab.com,bitbucket.org")
    return {h.strip().lower() for h in raw.split(",") if h.strip()}


def local_repos_allowed() -> bool:
    return os.getenv("SKILL_PASSPORT_ALLOW_LOCAL_REPOS", "0").lower() in ("1", "true", "yes")


@dataclass(frozen=True)
class RepoRef:
    url: str                      # canonical https://host/owner/repo (or the local path)
    host: Optional[str] = None
    owner: Optional[str] = None
    name: Optional[str] = None
    local_path: Optional[str] = None

    @property
    def clone_url(self) -> str:
        return f"https://{self.host}/{self.owner}/{self.name}.git"

    @property
    def is_github(self) -> bool:
        return self.host == "github.com"


def parse_repo_source(source: str, allow_local: bool = False) -> RepoRef:
    """
    Validate a repository reference. Only https URLs on allow-listed hosts are accepted
    (no credentials, ports, or internal hosts), so the server can't be used to fetch arbitrary URLs.
    Local paths are accepted only when explicitly allowed.
    """
    raw = (source or "").strip()
    if not raw:
        raise RepoSourceError("Repository URL is empty.")

    if re.match(r"^[a-zA-Z]:[\\/]", raw) or raw.startswith(("\\\\", "/", "./", "../")):
        if allow_local and os.path.isdir(raw):
            path = os.path.abspath(raw)
            return RepoRef(url=raw, local_path=path, name=os.path.basename(path.rstrip(os.sep)))
        raise RepoSourceError(f"Local repository paths are not allowed: '{raw}'. Link an https:// repository.")

    if allow_local and os.path.isdir(raw):
        path = os.path.abspath(raw)
        return RepoRef(url=raw, local_path=path, name=os.path.basename(path.rstrip(os.sep)))

    candidate = raw
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", candidate):
        candidate = "https://" + candidate
    parsed = urlparse(candidate)

    if parsed.scheme not in ("https", "http"):
        raise RepoSourceError(f"Unsupported repository URL scheme in '{raw}'. Use an https:// link.")
    if parsed.username or parsed.password or parsed.port:
        raise RepoSourceError("Repository URLs must not contain credentials or ports.")
    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if host not in allowed_hosts():
        raise RepoSourceError(
            f"'{host or raw}' is not a supported code host. Allowed: {', '.join(sorted(allowed_hosts()))}."
        )

    segments = [s for s in parsed.path.split("/") if s]
    if host == "gitlab.com" and "-" in segments:
        segments = segments[:segments.index("-")]
    elif host != "gitlab.com":
        segments = segments[:2]
    if len(segments) < 2:
        raise RepoSourceError(
            f"'{raw}' looks like a profile link, not a repository. Link a specific repository, e.g. https://{host}/user/project."
        )
    owner = "/".join(segments[:-1])
    name = segments[-1]
    if name.endswith(".git"):
        name = name[:-4]
    for part in owner.split("/") + [name]:
        if not NAME_PATTERN.match(part) or part in (".", ".."):
            raise RepoSourceError(f"Invalid repository path in '{raw}'.")

    return RepoRef(url=f"https://{host}/{owner}/{name}", host=host, owner=owner, name=name)


def clone_repo(ref: RepoRef, dest: str) -> None:
    timeout = int(os.getenv("SKILL_PASSPORT_CLONE_TIMEOUT_S", "120"))
    max_mb = int(os.getenv("SKILL_PASSPORT_MAX_REPO_MB", "500"))
    free_mb = shutil.disk_usage(os.path.dirname(os.path.abspath(dest))).free / (1024 * 1024)
    if free_mb < max_mb * 2:
        raise RepoAccessError("The server is low on disk space right now. Please try again later.")
    env = {
        **os.environ,
        "GIT_TERMINAL_PROMPT": "0",   # never block on a credential prompt for private repos
        "GIT_LFS_SKIP_SMUDGE": "1",
    }
    cmd = [
        "git", "-c", "credential.helper=", "clone", "--quiet", "--no-tags", "--single-branch",
        "--filter=blob:limit=2m", ref.clone_url, dest,
    ]
    try:
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        shutil.rmtree(dest, ignore_errors=True)
        raise RepoAccessError(f"Cloning {ref.url} took longer than {timeout}s. Try a smaller repository.") from exc
    except FileNotFoundError as exc:
        raise RepoAccessError("git is not installed on the server.") from exc

    if proc.returncode != 0:
        stderr = (proc.stderr or "").lower()
        if any(s in stderr for s in ("not found", "could not read username", "authentication", "terminal prompts disabled", "403")):
            reason = "the repository doesn't exist or is private. Only public repositories can be analysed - make it public, or use the Skill Challenge quiz instead."
        elif "could not resolve host" in stderr or "unable to access" in stderr:
            reason = "the server couldn't reach the code host (network problem)."
        else:
            reason = (proc.stderr or "unknown git error").strip().splitlines()[-1][:200]
        raise RepoAccessError(f"Could not clone {ref.url}: {reason}")

    size_mb = _dir_size_bytes(dest) / (1024 * 1024)
    if size_mb > max_mb:
        raise RepoAccessError(f"{ref.url} is {size_mb:.0f} MB, over the {max_mb} MB analysis limit.")


def _dir_size_bytes(path: str) -> int:
    total = 0
    for root, _, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total
