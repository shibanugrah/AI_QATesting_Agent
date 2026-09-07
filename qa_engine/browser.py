from __future__ import annotations

import base64
import io
import json
import os
import secrets as random_secrets
import shutil
import tempfile
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Literal

from qa_engine.domain import Attempt, Model, uid
from qa_engine.process import execute
from qa_engine.repository import worker_root
from qa_engine.security import PolicyBlocked


class JourneyOutput(Model):
    id: str
    profile: str
    status: Literal["SUCCEEDED", "FAILED", "ERROR", "BLOCKED"]
    duration_ms: int
    assertions: int
    console: list[dict[str, Any]]
    network: list[dict[str, Any]]
    accessibility: list[dict[str, Any]]
    error: str | None
    screenshot: str | None
    trace: str | None


class BrowserOutput(Model):
    schema_version: Literal[1]
    request_id: str
    project_id: str
    environment_id: str
    browser: Literal["chromium"]
    playwright_status: Literal["passed", "failed", "timedout", "interrupted"]
    tests: list[JourneyOutput]


class Broker:
    """Per-attempt private transport. Python policy authorizes every browser HTTP request."""

    def __init__(self, http):
        self.token = random_secrets.token_urlsafe(32)
        token = self.token

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_POST(self):
                self.connection.settimeout(5)
                if self.path != "/fetch" or self.headers.get("Authorization") != token:
                    self.send_error(403)
                    return
                try:
                    size = int(self.headers.get("Content-Length", "0"))
                    if not 0 < size <= http.project.policy.max_response_bytes:
                        raise PolicyBlocked("BROKER_BODY_LIMIT")
                    payload = json.loads(self.rfile.read(size))
                    response = http.request(
                        payload["url"],
                        payload["method"],
                        payload.get("headers"),
                        base64.b64decode(payload["body"], validate=True) if payload.get("body") else None,
                        follow=False,
                    )
                    data = {"status": response.status, "headers": response.headers, "body": base64.b64encode(response.body).decode()}
                    status = 200
                except PolicyBlocked as exc:
                    data, status = {"error": str(exc)}, 403
                except Exception:
                    data, status = {"error": "BROWSER_TRANSPORT_ERROR"}, 502
                encoded = json.dumps(data).encode()
                try:
                    self.send_response(status)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(encoded)))
                    self.end_headers()
                    self.wfile.write(encoded)
                except (BrokenPipeError, ConnectionResetError):
                    pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


def sanitize_trace(path, redactor, cap):
    def remove_payloads(value):
        if isinstance(value, dict):
            return {
                key: ""
                if key.lower() in {"body", "postdata", "postdatabuffer", "buffer", "cookies", "storagestate"}
                else remove_payloads(val)
                for key, val in value.items()
            }
        if isinstance(value, list):
            return [remove_payloads(v) for v in value]
        return value

    output = io.BytesIO()
    with zipfile.ZipFile(path) as archive, zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as target:
        total = 0
        for entry in archive.infolist():
            total += entry.file_size
            if total > cap or entry.file_size > cap:
                raise PolicyBlocked("TRACE_SIZE_LIMIT")
            name = entry.filename
            if ".." in Path(name).parts or name.startswith(("/", "\\")):
                raise PolicyBlocked("INVALID_TRACE_PATH")
            raw = archive.read(entry)
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                # No opaque browser resources may enter retained evidence.
                continue
            lines = []
            for line in text.splitlines():
                try:
                    lines.append(json.dumps(redactor.clean(remove_payloads(json.loads(line)))))
                except ValueError:
                    lines.append(redactor.text(line))
            target.writestr(name, "\n".join(lines))
    return output.getvalue()


def execute_browser(project, item, number, http, secret_provider, evidence):
    journey = next(j for j in project.journeys if item.id == item.kind + "-" + j.id)
    refs = {s.credential_ref for s in journey.steps if s.credential_ref}
    credentials = {ref: secret_provider.resolve(ref) for ref in refs}
    request_id = uid()
    with tempfile.TemporaryDirectory(prefix="qa-browser-") as folder, Broker(http) as broker:
        directory = Path(folder)
        os.chmod(directory, 0o700)
        request = {
            "schema_version": 1,
            "request_id": request_id,
            "project_id": project.id,
            "environment_id": project.environment,
            "kind": item.kind,
            "journey": journey.model_dump(),
            "timeout_ms": project.policy.timeout_seconds * 1000,
            "broker_url": f"http://127.0.0.1:{broker.server.server_port}/fetch",
            "broker_token": broker.token,
            "output_dir": str(directory),
        }
        request_path = directory / "request.json"
        request_path.write_text(json.dumps(request), encoding="utf-8")
        result = execute(
            [
                shutil.which("node") or "node",
                str(worker_root() / "node_modules/@playwright/test/cli.js"),
                "test",
                "--config",
                str(worker_root() / "playwright.config.ts"),
            ],
            worker_root(),
            timeout=project.policy.timeout_seconds * len(journey.profiles) + 25,
            cap=200_000,
            extra_env={"QA_WORKER_REQUEST": str(request_path), "QA_WORKER_CREDENTIALS": json.dumps(credentials)},
        )
        output_path = directory / "result.json"
        if result.timed_out or not output_path.exists() or output_path.stat().st_size > project.policy.max_artifact_bytes:
            return Attempt(number=number, status="ERROR", exit_code=result.exit_code, failure_code="BROWSER_WORKER_INCOMPLETE")
        try:
            output = BrowserOutput.model_validate_json(output_path.read_text(encoding="utf-8"))
        except ValueError:
            return Attempt(number=number, status="ERROR", exit_code=result.exit_code, failure_code="BROWSER_PROTOCOL_ERROR")
        profiles = {p.name for p in journey.profiles}
        if (
            (output.request_id, output.project_id, output.environment_id) != (request_id, project.id, project.environment)
            or len(output.tests) != len(profiles)
            or {t.profile for t in output.tests} != profiles
            or any(t.id != journey.id for t in output.tests)
        ):
            raise PolicyBlocked("BROWSER_PROTOCOL_IDENTITY_MISMATCH")
        artifacts = []
        for test in output.tests:
            for kind in ("screenshot", "trace"):
                value = getattr(test, kind)
                if not value:
                    if test.status == "SUCCEEDED":
                        test.status, test.error = "ERROR", "BROWSER_EVIDENCE_MISSING"
                    continue
                path = Path(value).resolve()
                if not path.is_relative_to(directory) or not path.is_file() or path.stat().st_size > project.policy.max_artifact_bytes:
                    raise PolicyBlocked("BROWSER_ARTIFACT_INVALID")
                data = (
                    sanitize_trace(path, evidence.redactor, project.policy.max_artifact_bytes * 4) if kind == "trace" else path.read_bytes()
                )
                extension = "zip" if kind == "trace" else "png"
                artifact = evidence.retain(f"{item.id}-{number}-{test.profile}.{extension}", data, kind)
                artifacts.append(artifact)
                setattr(test, kind, artifact.id)
        statuses = {t.status for t in output.tests}
        status = (
            "BLOCKED" if "BLOCKED" in statuses else "ERROR" if "ERROR" in statuses else "FAILED" if "FAILED" in statuses else "SUCCEEDED"
        )
        if status == "SUCCEEDED" and (result.exit_code != 0 or output.playwright_status != "passed"):
            status = "ERROR"
        return Attempt(
            number=number,
            status=status,
            exit_code=result.exit_code,
            evidence=artifacts,
            failure_code=None if status == "SUCCEEDED" else "BROWSER_" + status,
            details=evidence.redactor.clean(output.model_dump()),
        )
