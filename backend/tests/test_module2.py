import os
import tempfile
import git
import pytest
from app.module2_harvester import (
    GitBlameAnalyzer,
    ASTAnalyzer,
    TestDetector,
    ForkAndTemplateDetector,
    EvidenceHarvesterService
)
from app.schemas import EvidenceDocument

@pytest.fixture
def sample_git_repo():
    tmp_dir = tempfile.mkdtemp(prefix="test_repo_")
    repo = git.Repo.init(tmp_dir)

    # Configure user
    repo.config_writer().set_value("user", "name", "Priya S.").release()
    repo.config_writer().set_value("user", "email", "priya@example.com").release()

    # Create app/routes.py
    os.makedirs(os.path.join(tmp_dir, "app"), exist_ok=True)
    routes_py = os.path.join(tmp_dir, "app", "routes.py")
    with open(routes_py, "w") as f:
        f.write(
            "from fastapi import FastAPI, APIRouter\n"
            "app = FastAPI()\n"
            "router = APIRouter()\n\n"
            "@router.get('/health')\n"
            "def health():\n"
            "    try:\n"
            "        return {'status': 'healthy'}\n"
            "    except Exception:\n"
            "        return {'status': 'error'}\n"
        )
    repo.index.add([routes_py])
    repo.index.commit("Initial commit: Add FastAPI router and error handling")

    # Create tests/test_api.py
    os.makedirs(os.path.join(tmp_dir, "tests"), exist_ok=True)
    test_py = os.path.join(tmp_dir, "tests", "test_api.py")
    with open(test_py, "w") as f:
        f.write(
            "import pytest\n"
            "def test_health():\n"
            "    assert 1 == 1\n"
            "    assert True is True\n"
        )
    repo.index.add([test_py])
    repo.index.commit("Add unit tests with pytest assertions")

    yield tmp_dir

def test_ast_analyzer_detects_fastapi_and_routes(sample_git_repo):
    analyzer = ASTAnalyzer()
    res = analyzer.analyze_directory(sample_git_repo)
    assert "FastAPI" in res["frameworks_detected"]
    assert res["route_definitions_count"] >= 1
    assert res["has_error_handling"] is True

def test_test_detector_identifies_pytest(sample_git_repo):
    detector = TestDetector()
    res = detector.detect_tests(sample_git_repo)
    assert res["has_tests"] is True
    assert res["test_framework"] == "pytest"
    assert res["test_assertion_count"] >= 2
    assert res["test_file_count"] == 1

def test_git_blame_analyzer_authorship_pct(sample_git_repo):
    blame = GitBlameAnalyzer()
    res = blame.analyze_repo(sample_git_repo, candidate_email_or_name="Priya S.")
    assert res["candidate_authorship_pct"] > 90.0
    assert res["total_commits"] == 2
    assert "Python" in res["language_lines"]

def test_harvester_service_conforms_to_contract(sample_git_repo):
    harvester = EvidenceHarvesterService()
    doc: EvidenceDocument = harvester.harvest_repo(sample_git_repo, candidate_name="Priya S.")
    assert isinstance(doc, EvidenceDocument)
    assert doc.candidate_authorship_pct > 90.0
    assert doc.signals.has_tests is True
    assert doc.signals.test_framework == "pytest"
    assert "Python" in doc.skills_detected
    assert "FastAPI" in doc.skills_detected
