"""Owner-controlled fixtures only. No external project is selected or modified."""

import json
import subprocess
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from qa_engine.domain import APIEndpoint, Journey, Policy, Project, Step, Viewport


def make_repository(path: Path, broken=False, npm=False):
    path.mkdir(parents=True)
    (path / ".gitignore").write_text("__pycache__/\n.pytest_cache/\n*.egg-info/\nbuild/\ndist/\n.ruff_cache/\nstate.txt\n")
    (path / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\npythonpath=["."]\nmarkers=["integration: integration test", "regression: regression test"]\n'
    )
    (path / "app.py").write_text("def add(a, b):\n    return a " + ("-" if broken else "+") + " b\n")
    (path / "tests").mkdir()
    (path / "tests/test_app.py").write_text(
        "from app import add\nimport pytest\ndef test_add():\n    assert add(2, 3) == 5\n@pytest.mark.regression\ndef test_regression():\n    assert add(0, 0) == 0\n@pytest.mark.integration\ndef test_integration():\n    assert add(1, 1) == 2\n"
    )
    if npm:
        (path / "package.json").write_text(
            json.dumps(
                {
                    "name": "controlled-fixture",
                    "private": True,
                    "scripts": {"lint": "node lint.cjs", "typecheck": "node type.cjs", "build": "node build.cjs"},
                }
            )
        )
        for name in ("lint", "type", "build"):
            (path / (name + ".cjs")).write_text("process.exit(0);\n")
    for args in (
        ["init", "-q"],
        ["add", "."],
        ["-c", "user.name=QA Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "Controlled fixture baseline"],
    ):
        subprocess.run(["git", "-C", str(path), *args], check=True, capture_output=True, timeout=20)
    return path


def repository_project(path, project_id="python-fixture", required=None):
    return Project(
        id=project_id,
        repository=str(path),
        policy=Policy(
            required=required or ["unit"],
            allowed_commands=["pytest_unit", "pytest_integration", "pytest_regression", "npm_lint", "npm_type", "npm_build"],
            diagnostic_retries=1,
            timeout_seconds=15,
            regression_checks=["regression"],
        ),
    )


HTML = """<!doctype html><html lang="en"><head><title>Controlled QA fixture</title></head>
<body><main><h1>Staging login</h1><form id="login"><label for="username">Username</label><input id="username" autocomplete="username"><label for="password">Password</label><input id="password" type="password" autocomplete="current-password"><button type="submit">Sign in</button></form><p id="message" role="status">Ready</p>
<script>document.querySelector('#login').onsubmit=async(e)=>{e.preventDefault();const r=await fetch('/login',{method:'POST',body:JSON.stringify({username:document.querySelector('#username').value,password:document.querySelector('#password').value})});await r.text();document.querySelector('#message').textContent=r.ok?'Welcome':'Login failed';};</script>
</main></body></html>"""


@contextmanager
def web_fixture():
    state = {"broken": False, "requests": 0, "canary": "", "login_broken": False, "flaky": False}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def send(self, status, body, content_type="application/json", extra=None):
            payload = body.encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'")
            self.send_header("X-Content-Type-Options", "nosniff")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):
            state["requests"] += 1
            if self.path == "/redirect":
                self.send(302, "", extra={"Location": "http://169.254.169.254/latest/meta-data/"})
            elif self.path == "/health":
                broken = state["broken"] or (state["flaky"] and state["requests"] == 1)
                self.send(500 if broken else 200, json.dumps({"ok": not broken, "token": state["canary"], "message": state["canary"]}))
            elif self.path == "/noise":
                self.send(
                    200,
                    HTML.replace("</script>", "console.error('Controlled console error');fetch('/offline').catch(()=>{});</script>"),
                    "text/html",
                )
            elif self.path == "/offline":
                self.connection.close()
            elif self.path == "/a11y":
                self.send(200, HTML.replace('<label for="username">Username</label>', ""), "text/html")
            elif self.path == "/private":
                authorized = "qa_session=fixture-session" in self.headers.get("Cookie", "")
                self.send(
                    200 if authorized else 401, HTML.replace("Ready", "Private welcome" if authorized else "Unauthorized"), "text/html"
                )
            else:
                self.send(200, HTML, "text/html")

        def do_POST(self):
            state["requests"] += 1
            self.rfile.read(int(self.headers.get("Content-Length", 0)))
            self.send(
                401 if state["login_broken"] else 200,
                "{}",
                extra={"Set-Cookie": "qa_session=fixture-session; HttpOnly; SameSite=Strict; Path=/"},
            )

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", state
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def web_project(url, project_id="web-fixture", browser=False):
    from urllib.parse import urlsplit

    policy = Policy(
        required=["browser_e2e"] if browser else ["api"],
        allowed_hosts=["127.0.0.1"],
        allowed_ports=[urlsplit(url).port],
        allow_loopback=True,
        allow_mutation=browser,
        diagnostic_retries=0,
        timeout_seconds=8,
        regression_checks=["api"],
    )
    project = Project(id=project_id, policy=policy, api_endpoints=[APIEndpoint(id="health", url=url + "/health")])
    if browser:
        project.credentials = {"password": "QA_FIXTURE_PASSWORD"}
        project.journeys = [
            Journey(
                id="login",
                steps=[
                    Step(action="goto", value=url),
                    Step(action="fill", selector="#username", value="qa-fixture"),
                    Step(action="fill", selector="#password", credential_ref="password"),
                    Step(action="click", selector="button"),
                    Step(action="expect_text", selector="#message", value="Welcome"),
                ],
                profiles=[Viewport(), Viewport(name="mobile", width=390, height=844)],
            )
        ]
    return project
