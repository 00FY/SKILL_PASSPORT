from .git_crawler import GitBlameAnalyzer
from .ast_analyzer import ASTAnalyzer
from .test_detector import TestDetector
from .fork_detector import ForkAndTemplateDetector
from .github_api import GitHubClient
from .identity import IdentityMatcher
from .repo_source import RepoRef, RepoSourceError, RepoAccessError, parse_repo_source
from .harvester_service import EvidenceHarvesterService, merge_evidence

__all__ = [
    "GitBlameAnalyzer",
    "ASTAnalyzer",
    "TestDetector",
    "ForkAndTemplateDetector",
    "GitHubClient",
    "IdentityMatcher",
    "RepoRef",
    "RepoSourceError",
    "RepoAccessError",
    "parse_repo_source",
    "EvidenceHarvesterService",
    "merge_evidence",
]
