from __future__ import annotations

import json
import time
import ast
import hashlib
import http.client
import re
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from qa_engine.domain import Attempt, now
from qa_engine.process import execute
from qa_engine.repository import command_argv, package_data
from qa_engine.security import BudgetExceeded, PolicyBlocked


class Executors:
    def __init__(self, project, http, secrets, evidence):
        self.project, self.http, self.secrets, self.evidence = project, http, secrets, evidence

    def run(self, item, number):
        started = time.monotonic()
        started_at = now()
        try:
            if item.command_id:
                attempt = self.native(item, number)
            elif item.kind in {"api", "smoke", "security_headers"}:
                attempt = self.api(item, number)
            elif item.kind in {"browser_e2e", "accessibility", "web_diagnostics"}:
                from qa_engine.browser import execute_browser

                attempt = execute_browser(self.project, item, number, self.http, self.secrets, self.evidence)
            else:
                attempt = Attempt(number=number, status="BLOCKED", failure_code="NO_EXECUTOR")
        except PolicyBlocked as exc:
            attempt = Attempt(number=number, status="BLOCKED", failure_code=str(exc))
        except (OSError, TimeoutError, BudgetExceeded, http.client.HTTPException) as exc:
            attempt = Attempt(number=number, status="ERROR", failure_code=type(exc).__name__, details={"error": str(exc)})
        attempt.duration_ms = int((time.monotonic() - started) * 1000)
        attempt.started_at = started_at
        attempt.details = self.evidence.redactor.clean(attempt.details)
        summary = self.evidence.retain(f"{item.id}-{number}.json", attempt.model_dump(), "execution")
        attempt.evidence.append(summary)
        return attempt

    def native(self, item, number):
        if item.command_id not in self.project.policy.allowed_commands:
            raise PolicyBlocked("COMMAND_NOT_AUTHORIZED")
        artifacts, test_cases = [], []
        with tempfile.TemporaryDirectory(prefix="qa-native-") as folder:
            argv = command_argv(item.command_id)
            junit = Path(folder) / "junit.xml"
            if item.command_id.startswith("pytest_"):
                argv.append("--junitxml=" + str(junit))
            result = execute(
                argv,
                self.project.repository,
                timeout=self.project.policy.timeout_seconds,
                cap=min(1_000_000, self.project.policy.max_artifact_bytes // 2),
            )
            if junit.is_file() and junit.stat().st_size <= self.project.policy.max_artifact_bytes:
                xml = junit.read_text(encoding="utf-8")
                artifacts.append(self.evidence.retain(f"{item.id}-{number}-junit.xml", xml, "junit"))
                try:
                    for case in ET.fromstring(xml).iter("testcase"):
                        classname, name = case.get("classname", ""), case.get("name", "")
                        test_cases.append(
                            {
                                "id": classname + "::" + name,
                                "failed": case.find("failure") is not None,
                                "skipped": case.find("skipped") is not None,
                                "source_hash": test_source_hash(self.project.repository, classname, name),
                            }
                        )
                except ET.ParseError:
                    raise PolicyBlocked("INVALID_JUNIT_EVIDENCE")
        code = None
        status = "SUCCEEDED" if result.exit_code == 0 else "FAILED"
        npm_readiness = npm_execution_readiness(self.project.repository, item.command_id)
        node_test = node_test_result(self.project.repository, item.command_id, result.exit_code, result.stdout, result.stderr)
        if result.timed_out or result.truncated:
            status, code = "ERROR", "PROCESS_TIMEOUT" if result.timed_out else "OUTPUT_LIMIT_EXCEEDED"
        elif result.exit_code and npm_readiness:
            status, code = "ERROR", npm_readiness["reason"]
        elif node_test:
            status, code = node_test["status"], node_test["failure_code"]
        elif result.exit_code:
            if item.command_id.startswith("pytest") and result.exit_code in {2, 3, 4, 5}:
                status, code = "ERROR", "TEST_RUNNER_ERROR_OR_NO_TESTS"
            else:
                code = "NATIVE_CHECK_FAILED"
        details = {
            "argv": result.argv,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "truncated": result.truncated,
            "test_cases": test_cases,
        }
        if npm_readiness:
            details["execution_readiness"] = npm_readiness
        if node_test:
            details["test_result"] = {key: value for key, value in node_test.items() if key not in {"status", "failure_code"}}
        if item.command_id.startswith("pytest_") and status == "SUCCEEDED" and (not test_cases or all(t["skipped"] for t in test_cases)):
            status, code = "ERROR", "NO_EXECUTED_TEST_CASES"
        elif item.mandatory and status == "SUCCEEDED" and any(t["skipped"] for t in test_cases):
            status, code = "BLOCKED", "MANDATORY_SUITE_CONTAINS_SKIPPED_TESTS"
        if item.command_id == "pip_audit" and not result.timed_out:
            try:
                scan = json.loads(result.stdout)
                vulnerabilities = [v for d in scan["dependencies"] for v in d.get("vulns", [])]
                details["vulnerabilities"] = vulnerabilities
                if vulnerabilities:
                    status, code = "FAILED", "DEPENDENCY_VULNERABILITY"
                elif result.exit_code:
                    status, code = "ERROR", "SCANNER_ERROR"
            except (ValueError, KeyError, TypeError):
                status, code = "ERROR", "SCANNER_PROTOCOL_ERROR"
        return Attempt(number=number, status=status, exit_code=result.exit_code, failure_code=code, details=details, evidence=artifacts)

    def api(self, item, number):
        endpoints = (
            self.project.api_endpoints
            if item.kind == "security_headers"
            else [next(e for e in self.project.api_endpoints if item.id == item.kind + "-" + e.id)]
        )
        responses, passed = [], True
        for endpoint in endpoints:
            headers = {}
            if endpoint.credential_ref:
                headers["Authorization"] = "Bearer " + self.secrets.resolve(endpoint.credential_ref)
            response = self.http.request(endpoint.url, endpoint.method, headers)
            body = response.body.decode("utf-8", "replace")
            checks = {"status": response.status == endpoint.expected_status}
            if item.kind == "security_headers":
                checks.update(
                    {header: bool(response.headers.get(header)) for header in ["content-security-policy", "x-content-type-options"]}
                )
                if endpoint.url.startswith("https://"):
                    checks["strict-transport-security"] = bool(response.headers.get("strict-transport-security"))
            else:
                if endpoint.expected_text is not None:
                    checks["text"] = endpoint.expected_text in body
                for header, expected in endpoint.expected_headers.items():
                    checks["header:" + header.lower()] = response.headers.get(header.lower()) == expected
                if endpoint.expected_json:
                    try:
                        data = json.loads(body)
                        for key, expected in endpoint.expected_json.items():
                            value = data
                            for component in key.split("."):
                                value = value[int(component)] if isinstance(value, list) else value[component]
                            checks["json:" + key] = value == expected and type(value) is type(expected)
                    except (ValueError, KeyError, TypeError, IndexError):
                        checks["json"] = False
            passed = passed and all(checks.values())
            responses.append(
                {
                    "method": endpoint.method,
                    "url": response.url,
                    "status": response.status,
                    "duration_ms": response.duration_ms,
                    "assertions": checks,
                    "headers": response.headers,
                    "body": body[:4096],
                }
            )
        return Attempt(
            number=number,
            status="SUCCEEDED" if passed else "FAILED",
            failure_code=None if passed else "API_ASSERTION_FAILED",
            details={"responses": responses},
        )


NPM_SCRIPTS = {
    "npm_lint": "lint",
    "npm_type": "typecheck",
    "npm_build": "build",
    "npm_unit": "test",
    "npm_integration": "test:integration",
    "npm_regression": "test:regression",
}
NPM_TEST_COMMANDS = {"npm_unit", "npm_integration", "npm_regression"}


def npm_script(repository, command_id):
    script_name = NPM_SCRIPTS.get(command_id)
    script = package_data(repository).get("scripts", {}).get(script_name) if script_name else None
    return script if isinstance(script, str) else ""


def npm_execution_readiness(repository, command_id):
    """Describe a missing declared project-local npm tool without installing it."""
    script = npm_script(repository, command_id)
    match = re.match(r"\s*([@\w./-]+)", script)
    if not match:
        return None
    tool = Path(match.group(1)).name.lower()
    tool = re.sub(r"\.(?:cmd|exe|ps1)$", "", tool)
    manifest = package_data(repository)
    dependencies = {}
    for group in ("dependencies", "devDependencies", "optionalDependencies"):
        declared = manifest.get(group, {})
        if isinstance(declared, dict):
            dependencies.update(declared)
    if tool not in dependencies:
        return None
    bin_dir = Path(repository) / "node_modules" / ".bin"
    if any((bin_dir / (tool + suffix)).is_file() for suffix in ("", ".cmd", ".exe", ".ps1")):
        return None
    return {
        "state": "NOT_READY",
        "reason": "PROJECT_DEPENDENCIES_NOT_INSTALLED" if not (Path(repository) / "node_modules").is_dir() else "NATIVE_TOOL_UNAVAILABLE",
        "tool": tool,
    }


def node_test_result(repository, command_id, exit_code, stdout, stderr):
    """Interpret the stable summary protocol emitted by Node's built-in test runner."""
    if command_id not in NPM_TEST_COMMANDS or not re.match(r"\s*node(?:\.exe)?\s+--test(?:[=\s]|$)", npm_script(repository, command_id)):
        return None
    output = stdout + "\n" + stderr
    fields = {
        match.group(1): int(match.group(2))
        for match in re.finditer(r"(?m)^\s*#\s+(tests|suites|pass|fail|cancelled|skipped|todo)\s+(\d+)\s*$", output)
    }
    result = {"runner": "node:test", "summary": fields}
    if "tests" not in fields:
        failure_code = "TEST_RUNNER_ERROR" if exit_code else "TEST_EVIDENCE_UNINTERPRETABLE"
        return {**result, "status": "ERROR", "failure_code": failure_code}
    if fields["tests"] == 0 or fields.get("skipped", 0) == fields["tests"]:
        return {**result, "status": "ERROR", "failure_code": "NO_EXECUTED_TEST_CASES"}
    if fields.get("fail", 0) > 0:
        return {**result, "status": "FAILED", "failure_code": "TEST_FAILURE"}
    if exit_code:
        return {**result, "status": "ERROR", "failure_code": "TEST_RUNNER_ERROR"}
    if fields.get("pass", 0) + fields.get("skipped", 0) < fields["tests"]:
        return {**result, "status": "ERROR", "failure_code": "TEST_EVIDENCE_UNINTERPRETABLE"}
    return {**result, "status": "SUCCEEDED", "failure_code": None}


def test_source_hash(repository, classname, name):
    """Bind pytest failure identity to its original test body, including parameter cases."""
    root = Path(repository).resolve()
    components = classname.split(".")
    for count in range(len(components), 0, -1):
        path = (root / Path(*components[:count])).with_suffix(".py").resolve()
        if not path.is_relative_to(root) or not path.is_file():
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            function = name.split("[")[0]
            nodes = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == function]
            if len(nodes) == 1:
                return hashlib.sha256(ast.dump(nodes[0], include_attributes=False).encode()).hexdigest()
        except (ValueError, SyntaxError, UnicodeError):
            return None
    return None
