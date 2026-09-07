import json
import importlib.util
import socket
import sys
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from qa_engine import Engine, RunRequest
from qa_engine.browser import BrowserOutput
from qa_engine.domain import APIEndpoint, Policy, Project
from qa_engine.process import ProcessResult, environment, execute
from qa_engine.repository import command_argv, npm_cli
from qa_engine.security import BudgetExceeded, PolicyBlocked, Redactor, SafeHTTP, SecretProvider, URLGuard, fingerprint
from tests.engine_fixtures import make_repository, repository_project, web_fixture, web_project


@pytest.mark.parametrize("field,value", [("api_tests", []), ("command", "echo pass"), ("unknown", True)])
def test_unknown_project_config_rejected(field, value):
    with pytest.raises(ValidationError):
        Project.model_validate({"id": "p", "policy": {"required": ["unit"]}, field: value})


@pytest.mark.parametrize("field,value", [("timeout_seconds", "20"), ("allow_loopback", 1), ("diagnostic_retries", 3)])
def test_strict_policy(field, value):
    with pytest.raises(ValidationError):
        Policy.model_validate({"required": ["unit"], field: value})


@pytest.mark.parametrize("identifier", ["../b", "/root", "a/b", "a\\b", "", ".."])
def test_namespace_traversal_rejected(identifier):
    with pytest.raises(ValidationError):
        Project(id=identifier, policy=Policy(required=["unit"]))


def test_unenrolled_does_not_execute(tmp_path):
    with patch("subprocess.Popen") as proc:
        with pytest.raises(PolicyBlocked):
            Engine(tmp_path).run(RunRequest(project_id="unknown"))
        proc.assert_not_called()


@pytest.mark.parametrize("profile", ["api", "smoke"])
def test_profile_filter_before_executor(tmp_path, profile):
    with web_fixture() as (url, state):
        project = web_project(url)
        project.api_endpoints.append(APIEndpoint(id="smoke", url=url + "/health", tags=["smoke"]))
        project.policy.required = ["api", "smoke"]
        engine = Engine(tmp_path)
        engine.enroll(project)
        result = engine.run(RunRequest(project_id=project.id, profiles=[profile]))
        assert {c.kind for c in result.checks if c.attempts} == {profile}
        assert state["requests"] == 1
        assert result.gate.decision == "REVIEW_REQUIRED"


def test_unknown_command_id_never_executes(tmp_path):
    repo = make_repository(tmp_path / "repo")
    project = repository_project(repo)
    project.policy.allowed_commands = ["shell"]
    engine = Engine(tmp_path / "data")
    engine.enroll(project)
    with patch("qa_engine.executors.execute") as process:
        result = engine.verify_change(project.id)
    process.assert_not_called()
    assert result.gate.decision == "REVIEW_REQUIRED"


def test_python_build_uses_declared_pep517_backend_in_isolation(tmp_path):
    backend = "qa_engine_isolation_backend"
    assert importlib.util.find_spec(backend) is None
    wheel_dir = tmp_path / "wheels"
    wheel_dir.mkdir()
    wheel = wheel_dir / "qa_engine_isolation_backend-1.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr(
            backend + ".py",
            r"""from pathlib import Path
import zipfile


def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    wheel = Path(wheel_directory) / 'isolated_fixture-0.0.0-py3-none-any.whl'
    with zipfile.ZipFile(wheel, 'w') as output:
        output.writestr('isolated_fixture/__init__.py', '')
        output.writestr('isolated_fixture-0.0.0.dist-info/METADATA', 'Metadata-Version: 2.1\nName: isolated-fixture\nVersion: 0.0.0\n')
        output.writestr('isolated_fixture-0.0.0.dist-info/WHEEL', 'Wheel-Version: 1.0\nGenerator: fixture\nRoot-Is-Purelib: true\nTag: py3-none-any\n')
        output.writestr('isolated_fixture-0.0.0.dist-info/RECORD', '')
    return wheel.name
""",
        )
        archive.writestr("qa_engine_isolation_backend-1.0.dist-info/METADATA", "Metadata-Version: 2.1\nName: qa-engine-isolation-backend\nVersion: 1.0\n")
        archive.writestr("qa_engine_isolation_backend-1.0.dist-info/WHEEL", "Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n")
        archive.writestr("qa_engine_isolation_backend-1.0.dist-info/RECORD", "")
    project = tmp_path / "project"
    project.mkdir()
    (project / "pyproject.toml").write_text(
        """[build-system]
requires = [\"qa-engine-isolation-backend==1.0\"]
build-backend = \"qa_engine_isolation_backend\"

[project]
name = \"isolated-fixture\"
version = \"0.0.0\"
"""
    )
    result = execute(
        [*command_argv("python_build"), "--wheel"],
        project,
        timeout=30,
        extra_env={"PIP_NO_INDEX": "1", "PIP_FIND_LINKS": str(wheel_dir)},
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    assert (project / "dist" / "isolated_fixture-0.0.0-py3-none-any.whl").is_file()
    assert importlib.util.find_spec(backend) is None


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "http://user:pass@example.com",
        "http://example.com./",
        "http://example.com/#secret",
        "http://example.com/\r\nHeader:value",
        "http://example.com/?token=secret",
        "http://example.com\\@127.0.0.1",
    ],
)
def test_malformed_secret_urls_blocked(url):
    p = Project(id="p", policy=Policy(required=["api"], allowed_hosts=["example.com"]))
    with pytest.raises(PolicyBlocked):
        URLGuard(p).parse(url)


def test_dns_mixed_public_private_blocks():
    p = Project(id="p", policy=Policy(required=["api"], allowed_hosts=["example.com"]))
    addresses = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 80)),
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80)),
    ]
    with patch("socket.getaddrinfo", return_value=addresses), patch("socket.create_connection") as connect:
        with pytest.raises(PolicyBlocked):
            SafeHTTP(p).request("http://example.com/")
        connect.assert_not_called()


def test_request_budget():
    with web_fixture() as (url, state):
        p = web_project(url)
        p.policy.max_requests = 1
        client = SafeHTTP(p)
        assert client.request(url + "/health").status == 200
        with pytest.raises(BudgetExceeded):
            client.request(url + "/health")
        assert state["requests"] == 1


def test_response_size_limit():
    with web_fixture() as (url, state):
        state["canary"] = "x" * 3000
        p = web_project(url)
        p.policy.max_response_bytes = 1024
        with pytest.raises(BudgetExceeded):
            SafeHTTP(p).request(url + "/health")


def test_redaction_and_fingerprint():
    redactor = Redactor(["CANARY-9876"])
    value = redactor.clean(
        {"message": "CANARY-9876", "token": "unknown", "url": "https://a.test/path?foo=bar", "header": "Bearer raw-token"}
    )
    assert all(s not in json.dumps(value) for s in ["CANARY-9876", "unknown", "bar", "raw-token"])
    a = fingerprint("unit", "pytest", "failure", "2025-01-01T12:00:00Z request_id=ab12 http://a:8000", redactor)
    b = fingerprint("unit", "pytest", "failure", "2026-03-01T10:00:00Z request_id=ef89 http://a:9999", redactor)
    assert a == b


def test_secrets_project_binding(monkeypatch):
    monkeypatch.setenv("A_SECRET", "canary")
    a = Project(id="a", policy=Policy(required=["unit"]), credentials={"login": "A_SECRET"})
    b = Project(id="b", policy=Policy(required=["unit"]))
    assert SecretProvider(a).resolve("login") == "canary"
    with pytest.raises(PolicyBlocked):
        SecretProvider(b).resolve("login")
    assert "A_SECRET" not in environment()


def test_process_timeout_and_output_caps(tmp_path):
    result = execute([sys.executable, "-c", "import time;time.sleep(10)"], tmp_path, timeout=1)
    assert result.timed_out and result.duration_ms < 6000
    result = execute([sys.executable, "-c", "print('x'*10000)"], tmp_path, cap=100)
    assert result.truncated and len(result.stdout) == 100


def test_run_integrity_and_project_scoping(tmp_path):
    engine = Engine(tmp_path)
    for name in ["a", "b"]:
        engine.enroll(Project(id=name, policy=Policy(required=["unit"])))
    run = engine.run(RunRequest(project_id="a", dry_run=True))
    with pytest.raises(KeyError):
        engine.get_run("b", run.run_id)
    with engine.store.connect() as db:
        db.execute("UPDATE runs SET result=? WHERE id=?", ("{}", run.run_id))
    with pytest.raises(PolicyBlocked):
        engine.get_run("a", run.run_id)


def test_invalid_stage_transition(tmp_path):
    engine = Engine(tmp_path)
    engine.enroll(Project(id="a", policy=Policy(required=["unit"])))
    run = engine.run(RunRequest(project_id="a", dry_run=True))
    with pytest.raises(ValueError):
        engine.store.transition(run, 1, "RUNNING", Redactor())


def test_unknown_browser_protocol_rejected():
    with pytest.raises(ValidationError):
        BrowserOutput.model_validate({"schema_version": 2, "status": "PASS"})


def test_sqlite_constraints_and_migration(tmp_path):
    import sqlite3

    engine = Engine(tmp_path)
    with engine.store.connect() as db:
        assert db.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert db.execute("PRAGMA user_version").fetchone()[0] == 1
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("INSERT INTO environments VALUES('missing','local')")
    Engine(tmp_path)  # idempotent migration


def test_human_report_export(tmp_path):
    with web_fixture() as (url, _):
        engine = Engine(tmp_path / "data")
        p = engine.enroll(web_project(url))
        run = engine.run(RunRequest(project_id=p.id, profiles=["api"]))
        engine.review_report(p.id, run.run_id, "APPROVED", reviewer="Fixture Human")
        output = engine.export_report(p.id, run.run_id, tmp_path / "approved.md")
        assert Path(output).is_file()


def test_policy_condition_cannot_be_removed(tmp_path):
    from qa_engine.domain import Condition

    repo = make_repository(tmp_path / "repo")
    p = repository_project(repo)
    p.policy.conditional = [Condition(pattern="app.py", required=["regression"])]
    engine = Engine(tmp_path / "data")
    engine.enroll(p)
    plan = engine.plan(RunRequest(project_id=p.id, profiles=["unit"], advisory_additions=["lint"]))
    assert set(plan.required) == {"unit", "regression"}
    assert next(i for i in plan.items if i.kind == "regression").reason == "PROFILE_FILTERED"


def test_fix_rejects_missing_or_changed_original(tmp_path):
    with web_fixture() as (url, state):
        state["broken"] = True
        engine = Engine(tmp_path)
        p = engine.enroll(web_project(url))
        failed = engine.run(RunRequest(project_id=p.id, profiles=["api"]))
        state["broken"] = False
        p.api_endpoints[0].expected_status = 500
        engine.enroll(p)
        fixed = engine.verify_fix(p.id, failed.run_id)
        assert fixed.gate.decision != "PASS"
        assert "ORIGINAL_CHECK_MISSING_OR_CHANGED" in fixed.gate.reason_codes


def test_fix_cannot_delete_original_failing_test(tmp_path):
    repo = make_repository(tmp_path / "repo", broken=True)
    p = repository_project(repo)
    engine = Engine(tmp_path / "data")
    engine.enroll(p)
    failed = engine.verify_change(p.id, profiles=["unit"])
    (repo / "tests/test_app.py").write_text(
        "import pytest\ndef test_replacement():\n    assert True\n@pytest.mark.regression\ndef test_regression():\n    assert True\n"
    )
    fixed = engine.verify_fix(p.id, failed.run_id)
    assert fixed.gate.decision != "PASS"
    assert "ORIGINAL_TEST_REMOVED_CHANGED_OR_SKIPPED" in fixed.gate.reason_codes


def test_trace_header_pair_and_body_redaction(tmp_path):
    import zipfile
    from qa_engine.browser import sanitize_trace

    trace = tmp_path / "trace.zip"
    with zipfile.ZipFile(trace, "w") as archive:
        archive.writestr(
            "trace.trace",
            json.dumps({"params": {"headers": [{"name": "set-cookie", "value": "SECRET_SESSION"}], "body": "BASE64_SECRET_PAYLOAD"}}),
        )
    import io

    with zipfile.ZipFile(io.BytesIO(sanitize_trace(trace, Redactor(), 10000))) as output:
        value = output.read("trace.trace")
    assert b"SECRET_SESSION" not in value and b"BASE64_SECRET_PAYLOAD" not in value


def test_mandatory_suite_skip_prevents_pass(tmp_path):
    repo = make_repository(tmp_path / "repo")
    (repo / "tests/test_skip.py").write_text(
        "import pytest\n@pytest.mark.skip(reason='not executed')\ndef test_required():\n    assert True\n"
    )
    project = repository_project(repo)
    engine = Engine(tmp_path / "data")
    engine.enroll(project)
    result = engine.verify_change(project.id, profiles=["unit"])
    assert result.gate.decision == "REVIEW_REQUIRED"
    assert result.checks[0].reason == "MANDATORY_SUITE_CONTAINS_SKIPPED_TESTS"


def test_canonical_json_tamper_prevents_pass(tmp_path):
    with web_fixture() as (url, _):
        engine = Engine(tmp_path)
        project = engine.enroll(web_project(url))
        result = engine.run(RunRequest(project_id=project.id, profiles=["api"]))
        canonical = engine.store.root / "projects" / project.id / "runs" / result.run_id / "result.json"
        canonical.write_text('{"gate":"PASS"}')
        assert engine.gate(project.id, result.run_id).decision == "REVIEW_REQUIRED"


def test_plan_machine_output_redacts_context(tmp_path, monkeypatch):
    monkeypatch.setenv("QA_PLAN_SECRET", "PLAN-CANARY-2137")
    engine = Engine(tmp_path)
    engine.enroll(Project(id="p", policy=Policy(required=["unit"]), credentials={"test_secret": "QA_PLAN_SECRET"}))
    plan = engine.plan(RunRequest(project_id="p", dry_run=True, context="PLAN-CANARY-2137 password=another-secret"))
    assert "PLAN-CANARY-2137" not in plan.model_dump_json()
    assert "another-secret" not in plan.model_dump_json()


def test_npm_unix_layout_discovery(tmp_path):
    from qa_engine.repository import npm_cli

    node = tmp_path / "bin/node"
    node.parent.mkdir()
    node.write_text("")
    npm = tmp_path / "lib/node_modules/npm/bin/npm-cli.js"
    npm.parent.mkdir(parents=True)
    npm.write_text("")
    with patch("qa_engine.repository.shutil.which", side_effect=lambda name: str(node) if name == "node" else None):
        assert npm_cli() == str(npm)


def test_mixed_project_executes_both_native_unit_suites(tmp_path):
    repo = make_repository(tmp_path / "repo", npm=True)
    package = json.loads((repo / "package.json").read_text())
    package["scripts"]["test"] = "node test.cjs"
    (repo / "package.json").write_text(json.dumps(package))
    (repo / "test.cjs").write_text("console.error('frontend regression');process.exit(1);")
    project = repository_project(repo)
    project.policy.allowed_commands.append("npm_unit")
    engine = Engine(tmp_path / "data")
    engine.enroll(project)
    result = engine.verify_change(project.id, profiles=["unit"])
    assert result.gate.decision == "FAIL"
    assert {c.id for c in result.checks} == {"unit-pytest_unit", "unit-npm_unit"}
    assert next(c for c in result.checks if c.id == "unit-pytest_unit").status == "SUCCEEDED"
    assert next(c for c in result.checks if c.id == "unit-npm_unit").status == "FAILED"


@pytest.mark.skipif(not npm_cli(), reason="Node/npm is unavailable")
@pytest.mark.parametrize("kind,script", [("unit", "test"), ("integration", "test:integration"), ("regression", "test:regression")])
def test_node_builtin_runner_zero_tests_cannot_succeed(tmp_path, kind, script):
    repo = make_repository(tmp_path / "repo", npm=True)
    package = json.loads((repo / "package.json").read_text())
    package["scripts"][script] = "node --test"
    (repo / "package.json").write_text(json.dumps(package))
    project = repository_project(repo, required=[kind])
    project.policy.diagnostic_retries = 0
    project.policy.allowed_commands.append("npm_" + kind)
    engine = Engine(tmp_path / "data")
    engine.enroll(project)

    result = engine.verify_change(project.id, profiles=[kind])

    check = next(c for c in result.checks if c.id == f"{kind}-npm_{kind}")
    assert check.attempts[0].exit_code == 0
    assert check.status == "ERROR"
    assert check.classification == "INFRASTRUCTURE_ERROR"
    assert check.reason == "NO_EXECUTED_TEST_CASES"
    assert check.attempts[0].details["test_result"]["runner"] == "node:test"
    assert check.attempts[0].details["test_result"]["summary"]["tests"] == 0
    assert result.gate.decision != "PASS"
    assert "MANDATORY_CHECK_NOT_EXECUTED_SUCCESSFULLY" in result.gate.reason_codes


@pytest.mark.parametrize(
    "output",
    [
        "'eslint' is not recognized as an internal or external command, operable program or batch file.",
        "sh: 1: eslint: not found",
    ],
)
def test_missing_project_lint_tool_is_environment_error_with_evidence(tmp_path, output):
    repo = make_repository(tmp_path / "repo", npm=True)
    package = json.loads((repo / "package.json").read_text())
    package["scripts"]["lint"] = "eslint src --ext .js"
    package["devDependencies"] = {"eslint": "^9.0.0"}
    (repo / "package.json").write_text(json.dumps(package))
    project = repository_project(repo, required=["lint"])
    project.policy.diagnostic_retries = 0
    engine = Engine(tmp_path / "data")
    engine.enroll(project)
    process = ProcessResult(
        argv=command_argv("npm_lint"),
        exit_code=1,
        stdout="",
        stderr=output,
        duration_ms=1,
    )

    with patch("qa_engine.executors.execute", return_value=process):
        result = engine.verify_change(project.id, profiles=["lint"])

    assert result.checks, result.model_dump_json(indent=2)
    check = next(c for c in result.checks if c.kind == "lint")
    assert check.status == "ERROR"
    assert check.classification == "INFRASTRUCTURE_ERROR"
    assert check.reason == "PROJECT_DEPENDENCIES_NOT_INSTALLED"
    assert check.classification != "PRODUCT_REGRESSION"
    assert check.attempts[0].details["argv"] == process.argv
    assert check.attempts[0].details["stderr"] == output
    assert check.attempts[0].evidence
    assert result.gate.decision == "REVIEW_REQUIRED"


def test_child_outliving_parent_is_terminated(tmp_path):
    import time

    script = "import time;from pathlib import Path;time.sleep(3);Path('escaped.txt').write_text('escaped')"
    parent = "import subprocess,sys;subprocess.Popen([sys.executable,'-c'," + repr(script) + "])"
    result = execute([sys.executable, "-c", parent], tmp_path, timeout=1)
    assert result.timed_out
    time.sleep(3)
    assert not (tmp_path / "escaped.txt").exists()
