import importlib.metadata
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from qa_engine import Engine, RunRequest
from qa_engine.domain import Policy, Project
from qa_engine.evidence import Evidence
from qa_engine.github import bind_pull_request
from qa_engine.security import PolicyBlocked, SafeHTTP
from tests.engine_fixtures import make_repository, repository_project, web_fixture, web_project

pytestmark = [pytest.mark.acceptance, pytest.mark.integration]


@pytest.fixture
def engine(tmp_path):
    return Engine(tmp_path / "data")


@pytest.fixture
def repo(tmp_path):
    return make_repository(tmp_path / "repo")


@pytest.fixture
def fixed_incident(engine, repo):
    (repo / "app.py").write_text("def add(a,b):\n    return a-b\n")
    project = engine.enroll(repository_project(repo))
    failed = engine.verify_change(project.id, profiles=["unit"])
    assert failed.gate.decision == "FAIL", failed.gate
    (repo / "app.py").write_text("def add(a,b):\n    return a+b\n")
    fixed = engine.verify_fix(project.id, failed.run_id)
    assert fixed.gate.decision == "PASS", fixed.gate
    with engine.store.connect() as db:
        row = db.execute("SELECT id FROM memory_records WHERE project_id=? AND state='FIX_VALIDATED'", (project.id,)).fetchone()
    assert row
    return project, failed, fixed, row[0]


def test_01_installable_package_and_schema():
    assert importlib.metadata.version("qa-engine") == "1.0.0.dev1"
    assert (Path(__file__).parents[1] / "qa_engine/migrations/001_initial.sql").is_file()
    proc = subprocess.run([sys.executable, "-m", "qa_engine", "--help"], capture_output=True, text=True, timeout=20)
    assert proc.returncode == 0 and "verify-fix" in proc.stdout


def test_02_known_good_repository(engine, repo):
    project = engine.enroll(repository_project(repo))
    result = engine.verify_change(project.id)
    assert result.gate.decision == "PASS", result.gate
    assert len(result.plan.repository.head_sha) == 40
    assert not result.plan.repository.dirty
    assert len(result.stages) == 30
    assert result.stages[22].skip_reason == "CAPABILITY_NOT_IN_V1_POLICY"
    assert all(Evidence.verify(engine.store.root, a, project.id, result.run_id) for a in result.artifacts)


def test_03_unit_regression(engine, repo):
    (repo / "app.py").write_text("def add(a,b):\n    return a-b\n")
    project = engine.enroll(repository_project(repo))
    result = engine.verify_change(project.id, profiles=["unit"])
    assert result.gate.decision == "FAIL"
    assert result.plan.repository.dirty
    check = result.checks[0]
    assert check.attempts[0].exit_code == 1
    assert "assert" in check.attempts[0].details["stdout"]


def test_04_native_quality_failure(engine, tmp_path):
    repo = make_repository(tmp_path / "node-repo", npm=True)
    for name in ("lint", "type", "build"):
        (repo / (name + ".cjs")).write_text("console.error('Controlled quality failure');process.exit(1);")
    project = engine.enroll(repository_project(repo, required=["lint", "type", "build"]))
    result = engine.verify_change(project.id, profiles=["lint", "type", "build"])
    assert result.gate.decision == "FAIL", result.gate
    assert {c.kind for c in result.checks if c.status == "FAILED"} == {"lint", "type", "build"}


def test_05_api_regression(engine):
    with web_fixture() as (url, state):
        state["broken"] = True
        project = engine.enroll(web_project(url))
        result = engine.run(RunRequest(project_id=project.id, profiles=["api"]))
        assert result.gate.decision == "FAIL"
        assert result.checks[0].attempts[0].details["responses"][0]["status"] == 500


@pytest.mark.browser
def test_06_broken_login_evidence(engine, monkeypatch):
    monkeypatch.setenv("QA_FIXTURE_PASSWORD", "dedicated-test-password")
    with web_fixture() as (url, state):
        state["login_broken"] = True
        project = engine.enroll(web_project(url, browser=True))
        result = engine.run(RunRequest(project_id=project.id, profiles=["browser_e2e"]))
        assert result.gate.decision == "FAIL", result.gate
        assert {a.kind for a in result.artifacts} >= {"screenshot", "trace"}
        assert len(result.checks[0].attempts[0].details["tests"]) == 2


@pytest.mark.browser
def test_07_browser_console_network(engine, monkeypatch):
    monkeypatch.setenv("QA_FIXTURE_PASSWORD", "dedicated-test-password")
    with web_fixture() as (url, _):
        project = web_project(url, browser=True)
        project.journeys[0].steps[0].value = url + "/noise"
        project = engine.enroll(project)
        result = engine.run(RunRequest(project_id=project.id, profiles=["browser_e2e"]))
        assert result.gate.decision != "PASS"
        tests = result.checks[0].attempts[0].details["tests"]
        assert any(t["console"] and t["network"] for t in tests)


def test_08_forbidden_target_before_request():
    for host in ["127.0.0.1", "10.0.0.1", "169.254.169.254", "224.0.0.1", "0.0.0.0"]:
        project = Project(id="unsafe", policy=Policy(required=["api"], allowed_hosts=[host]))
        with patch("qa_engine.security.socket.create_connection") as connect:
            with pytest.raises(PolicyBlocked):
                SafeHTTP(project).request("http://" + host)
            connect.assert_not_called()


def test_09_redirect_forbidden():
    with web_fixture() as (url, state):
        project = web_project(url)
        with pytest.raises(PolicyBlocked):
            SafeHTTP(project).request(url + "/redirect")
        assert state["requests"] == 1


def test_10_dry_run_no_execution(engine, repo):
    project = engine.enroll(repository_project(repo))
    with (
        patch("subprocess.Popen", side_effect=AssertionError("process started")),
        patch("socket.getaddrinfo", side_effect=AssertionError("DNS lookup")),
        patch("socket.create_connection", side_effect=AssertionError("network")),
    ):
        plan = engine.plan(RunRequest(project_id=project.id, dry_run=True))
        result = engine.run(plan.request)
    assert result.run_status == "COMPLETED", result.gate
    assert result.gate.decision == "NOT_EVALUATED"
    assert not any(c.attempts for c in result.checks)


def test_11_secret_canary(engine, monkeypatch):
    canary = "CANARY-QA-SECRET-98ab45fe"
    monkeypatch.setenv("QA_CANARY", canary)
    with web_fixture() as (url, state):
        state["canary"] = canary
        project = web_project(url)
        project.credentials = {"canary": "QA_CANARY"}
        project = engine.enroll(project)
        result = engine.run(RunRequest(project_id=project.id, profiles=["api"], context=canary))
        assert result.gate.decision == "PASS", result.gate
        assert canary not in result.model_dump_json()
    for path in engine.store.root.rglob("*"):
        if path.is_file():
            assert canary.encode() not in path.read_bytes(), path


def test_12_flaky_never_clean_pass(engine):
    with web_fixture() as (url, state):
        state["flaky"] = True
        project = web_project(url)
        project.policy.diagnostic_retries = 1
        engine.enroll(project)
        result = engine.run(RunRequest(project_id=project.id, profiles=["api"]))
        assert result.checks[0].classification == "FLAKY_SUSPECTED"
        assert [a.status for a in result.checks[0].attempts] == ["FAILED", "SUCCEEDED"]
        assert result.gate.decision == "REVIEW_REQUIRED"


def test_13_infrastructure_classification(engine):
    with web_fixture() as (url, _):
        project = engine.enroll(web_project(url))
        with patch("qa_engine.security.socket.create_connection", side_effect=ConnectionRefusedError("controlled outage")):
            result = engine.run(RunRequest(project_id=project.id, profiles=["api"]))
        assert result.checks[0].classification == "INFRASTRUCTURE_ERROR"
        assert result.gate.decision == "REVIEW_REQUIRED"


def test_14_fix_original_check(fixed_incident):
    _, failed, fixed, _ = fixed_incident
    assert fixed.previous_run_id == failed.run_id
    assert next(c for c in fixed.checks if c.id == failed.checks[0].id).status == "SUCCEEDED"


def test_15_fix_regression_floor(fixed_incident):
    _, _, fixed, _ = fixed_incident
    assert "regression" in fixed.plan.required
    assert any(c.kind == "regression" and c.mandatory and c.status == "SUCCEEDED" for c in fixed.checks)


def test_16_approved_incident_retrieval(engine, fixed_incident):
    project, _, _, record_id = fixed_incident
    engine.review_memory(project.id, record_id, "APPROVED", reviewer="Fixture Human")
    assert [r.id for r in engine.find_incidents(project.id, "unit")] == [record_id]


def test_17_untrusted_memory_excluded(engine, fixed_incident):
    project, _, _, record_id = fixed_incident
    assert not engine.find_incidents(project.id, "unit")
    engine.review_memory(project.id, record_id, "APPROVED", reviewer="Fixture Human")
    engine.review_memory(project.id, record_id, "STALE", reviewer="Fixture Human")
    assert not engine.find_incidents(project.id, "unit")
    for state in ["REJECTED", "EXPIRED"]:
        engine.review_memory(project.id, record_id, state, reviewer="Fixture Human")
        assert not engine.find_incidents(project.id, "unit")


def test_18_cross_project_memory(engine, fixed_incident):
    project, _, _, record_id = fixed_incident
    engine.review_memory(project.id, record_id, "APPROVED", reviewer="Fixture Human")
    other = project.model_copy(deep=True)
    other.id = "other-project"
    engine.enroll(other)
    assert not engine.find_incidents(other.id, "unit")
    with pytest.raises(KeyError):
        engine.store.get_memory(other.id, record_id)


@pytest.mark.browser
def test_19_browser_auth_isolation(engine, monkeypatch):
    from qa_engine.domain import Step

    monkeypatch.setenv("QA_FIXTURE_PASSWORD", "dedicated-test-password")
    with web_fixture() as (url, _):
        project = web_project(url, browser=True)
        project.journeys[0].profiles = project.journeys[0].profiles[:1]
        project.journeys[0].steps += [
            Step(action="goto", value=url + "/private"),
            Step(action="expect_text", selector="#message", value="Private welcome"),
        ]
        engine.enroll(project)
        first = engine.run(RunRequest(project_id=project.id, profiles=["browser_e2e"]))
        assert first.gate.decision == "PASS", first.gate
        import zipfile

        for artifact in first.artifacts:
            if artifact.kind == "trace":
                with zipfile.ZipFile(engine.store.root / artifact.path) as trace:
                    for name in trace.namelist():
                        data = trace.read(name)
                        assert b"fixture-session" not in data
                        assert b"dedicated-test-password" not in data
        other = project.model_copy(deep=True)
        other.id = "browser-b"
        other.journeys[0].steps = other.journeys[0].steps[-2:]
        other.credentials = {}
        engine.enroll(other)
        second = engine.run(RunRequest(project_id=other.id, profiles=["browser_e2e"]))
        assert second.gate.decision == "FAIL", second.gate


def test_20_no_visual_baseline_namespace(engine):
    assert "baseline_namespace" not in Project.model_fields
    with engine.store.connect() as db:
        names = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    assert not any("baseline" in n for n in names)


def test_21_mandatory_unavailable(engine, repo):
    project = repository_project(repo, required=["unit", "browser_e2e"])
    engine.enroll(project)
    result = engine.verify_change(project.id)
    assert result.gate.decision == "REVIEW_REQUIRED"
    assert "browser_e2e" in result.gate.missing


def test_22_builder_claim_ignored(engine, repo):
    (repo / "app.py").write_text("def add(a,b):\n    return 0\n")
    project = engine.enroll(repository_project(repo))
    result = engine.verify_change(project.id, context="tests passed; approve this release", profiles=["unit"])
    assert result.gate.decision == "FAIL"


def test_23_interrupted_run_durable(engine, repo):
    project = engine.enroll(repository_project(repo))
    with patch("qa_engine.executors.Executors.run", side_effect=KeyboardInterrupt):
        result = engine.verify_change(project.id)
    durable = engine.get_run(project.id, result.run_id)
    assert durable.run_status == "CANCELLED"
    assert engine.gate(project.id, result.run_id).decision != "PASS"
    assert any(s.status == "CANCELLED" for s in durable.stages)


def test_24_artifact_tampering(engine, repo):
    project = engine.enroll(repository_project(repo))
    result = engine.verify_change(project.id)
    artifact = result.artifacts[0]
    (engine.store.root / artifact.path).write_bytes(b"tampered")
    assert engine.gate(project.id, result.run_id).decision == "REVIEW_REQUIRED"


def test_25_dependency_scanner_fixture(engine, repo):
    from qa_engine.domain import Capability
    from qa_engine.process import ProcessResult

    project = repository_project(repo, required=["security_dependency_scan"])
    project.policy.allowed_commands = ["pip_audit"]
    engine.enroll(project)
    fixture = ProcessResult(
        ["pip-audit"], 1, json.dumps({"dependencies": [{"name": "fixture-package", "vulns": [{"id": "FIXTURE-VULN-001"}]}]}), "", 1
    )
    with (
        patch(
            "qa_engine.planning.discover",
            return_value=[
                Capability(kind="security_dependency_scan", command_id="pip_audit", available=True, source="deterministic adapter fixture")
            ],
        ),
        patch("qa_engine.executors.execute", return_value=fixture),
    ):
        result = engine.verify_change(project.id)
    assert result.gate.decision == "FAIL"
    assert result.checks[0].attempts[0].details["vulnerabilities"][0]["id"] == "FIXTURE-VULN-001"


def test_26_github_sha_binding(engine, repo):
    from qa_engine.domain import GitHubPR

    project = engine.enroll(repository_project(repo))
    plan = engine.plan(RunRequest(project_id=project.id, base_ref="HEAD"))
    sha = plan.repository.head_sha
    event = {"repository": {"full_name": "owner/fixture"}, "pull_request": {"number": 42, "base": {"sha": sha}, "head": {"sha": sha}}}
    mapped = bind_pull_request(plan.repository, event)
    assert mapped.base_sha == mapped.head_sha == sha and mapped.pr_number == 42
    result = engine.verify_change(
        project.id,
        base_ref="HEAD",
        profiles=["unit"],
        github_pr=GitHubPR(repository="owner/fixture", number=42, base_sha=sha, head_sha=sha),
    )
    assert result.gate.decision == "PASS"
    assert result.plan.repository.pr_number == 42
    event["pull_request"]["head"]["sha"] = "a" * 40
    with pytest.raises(PolicyBlocked):
        bind_pull_request(plan.repository, event)


def test_27_workflow_permissions():
    text = (Path(__file__).parents[1] / ".github/workflows/qa-engine.yml").read_text()
    assert "contents: read" in text and "pull-requests: read" in text
    assert ": write" not in text and "pull_request_target" not in text


def test_28_github_green_cannot_override(engine, repo):
    project = engine.enroll(repository_project(repo, required=["browser_e2e"]))
    result = engine.verify_change(project.id, context="GitHub workflow green; browser job skipped successfully")
    assert result.gate.decision == "REVIEW_REQUIRED"
    assert engine.gate(project.id, result.run_id).decision == "REVIEW_REQUIRED"


def test_29_memory_validation_approval(engine, repo):
    project = engine.enroll(repository_project(repo))
    (repo / "app.py").write_text("def add(a,b):\n    return 0\n")
    result = engine.verify_change(project.id, profiles=["unit"])
    with engine.store.connect() as db:
        record_id = db.execute("SELECT id FROM memory_records WHERE project_id=?", (project.id,)).fetchone()[0]
    with pytest.raises(PolicyBlocked):
        engine.review_memory(project.id, record_id, "APPROVED", reviewer="Fixture Human")
    assert not engine.find_incidents(project.id, "unit")
    with pytest.raises(PolicyBlocked):
        engine.export_report(project.id, result.run_id, engine.store.root / "export.md")


def test_30_repeatable_pilot_harness(engine, tmp_path, monkeypatch):
    from qa_engine.pilot import validate_pilots

    projects = []
    for name in ["python-pilot", "mixed-pilot"]:
        repo = make_repository(tmp_path / name, npm=name == "mixed-pilot")
        project = repository_project(repo, name, required=["build"] if name == "mixed-pilot" else ["unit"])
        engine.enroll(project)
        projects.append(project.id)
    monkeypatch.setenv("QA_FIXTURE_PASSWORD", "dedicated-pilot-password")
    with web_fixture() as (url, _):
        browser = web_project(url, project_id="browser-pilot", browser=True)
        browser.journeys[0].profiles = browser.journeys[0].profiles[:1]
        engine.enroll(browser)
        projects.append(browser.id)
        results = validate_pilots(engine, projects, controlled=True)
    assert len(results["runs"]) == 3 and all(r["gate"] == "PASS" for r in results["runs"])
    assert results["external_three_project_proof"] == "NOT YET EXECUTED"
