from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import shutil
import sys
import tomllib
from pathlib import Path

from qa_engine.domain import Capability, Project, RepositoryIdentity
from qa_engine.process import execute
from qa_engine.security import PolicyBlocked


def git(root, *args):
    result = execute(
        ["git", "--no-optional-locks", "-c", "core.fsmonitor=false", "-C", str(root), *args], cwd=root, timeout=20, cap=10_000_000
    )
    if result.exit_code or result.timed_out or result.truncated:
        raise PolicyBlocked("GIT_SNAPSHOT_UNAVAILABLE")
    return result.stdout.strip()


def resolve_ref(root, ref):
    if not ref or ref.startswith("-") or len(ref) > 200 or re.search(r"[\s\x00]", ref):
        raise PolicyBlocked("INVALID_GIT_REF")
    return git(root, "rev-parse", "--verify", "--end-of-options", ref + "^{commit}")


def snapshot(root, base=None, head="HEAD"):
    root = Path(root).resolve()
    top = Path(git(root, "rev-parse", "--show-toplevel")).resolve()
    if top != root:
        raise PolicyBlocked("ENROLLED_PATH_MUST_BE_REPOSITORY_ROOT")
    actual = resolve_ref(root, "HEAD")
    head_sha = resolve_ref(root, head)
    if actual != head_sha:
        raise PolicyBlocked("REQUESTED_HEAD_NOT_CHECKED_OUT")
    base_sha = resolve_ref(root, base) if base else None
    dirty_diff = git(root, "diff", "--no-ext-diff", "--no-textconv", "--binary", "HEAD", "--")
    status = git(root, "status", "--porcelain=v1", "--untracked-files=all")
    dirty_files = git(root, "diff", "--name-only", "--no-ext-diff", "--no-textconv", "HEAD", "--").splitlines()
    changed = git(root, "diff", "--name-only", "--no-ext-diff", "--no-textconv", base_sha, head_sha, "--").splitlines() if base_sha else []
    untracked = git(root, "ls-files", "--others", "--exclude-standard").splitlines()
    if len(untracked) > 1000:
        raise PolicyBlocked("WORKSPACE_SNAPSHOT_BUDGET")
    hasher = hashlib.sha256(dirty_diff.encode())
    total = 0
    for filename in sorted(untracked):
        path = (root / filename).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise PolicyBlocked("WORKSPACE_UNTRACKED_UNSAFE")
        total += path.stat().st_size
        if total > 10_000_000:
            raise PolicyBlocked("WORKSPACE_SNAPSHOT_BUDGET")
        hasher.update(filename.encode())
        hasher.update(path.read_bytes())
    remote_result = execute(["git", "-C", str(root), "config", "--get", "remote.origin.url"], root, timeout=10)
    remote = remote_result.stdout.strip() if remote_result.exit_code == 0 else ""
    github = re.search(r"github\.com[:/]([\w.-]+/[\w.-]+?)(?:\.git)?$", remote)
    return RepositoryIdentity(
        path=str(root),
        head_sha=head_sha,
        base_sha=base_sha,
        branch=git(root, "rev-parse", "--abbrev-ref", "HEAD"),
        remote=remote,
        dirty=bool(status),
        dirty_diff_hash=hasher.hexdigest(),
        changed_files=sorted(set(changed + dirty_files + untracked)),
        github_repository=github.group(1) if github else None,
    )


def package_data(root):
    path = Path(root) / "package.json"
    if not path.is_file():
        return {}
    if path.stat().st_size > 1_000_000:
        raise PolicyBlocked("MANIFEST_SIZE_LIMIT")
    return json.loads(path.read_text(encoding="utf-8"))


def discover(project: Project):
    capabilities = []
    if project.repository:
        root = Path(project.repository)
        pyproject = root / "pyproject.toml"
        config = tomllib.loads(pyproject.read_text(encoding="utf-8")) if pyproject.exists() else {}
        tools = config.get("tool", {})
        pytest_found = (root / "pytest.ini").exists() or "pytest" in tools or (root / "tests").is_dir()
        if pytest_found:
            for kind, marker in [("unit", None), ("integration", "integration"), ("regression", "regression")]:
                markers = tools.get("pytest", {}).get("ini_options", {}).get("markers", [])
                has = marker is None or any(str(m).split(":")[0].strip() == marker for m in markers)
                if has:
                    capabilities.append(
                        Capability(
                            kind=kind,
                            command_id="pytest_" + kind,
                            available=importlib.util.find_spec("pytest") is not None,
                            source="pytest configuration",
                        )
                    )
        if (root / "ruff.toml").exists() or "ruff" in tools:
            capabilities.append(
                Capability(
                    kind="lint", command_id="ruff", available=importlib.util.find_spec("ruff") is not None, source="ruff configuration"
                )
            )
        if (root / "mypy.ini").exists() or "mypy" in tools:
            capabilities.append(
                Capability(
                    kind="type", command_id="mypy", available=importlib.util.find_spec("mypy") is not None, source="mypy configuration"
                )
            )
        if "build-system" in config:
            capabilities.append(
                Capability(
                    kind="build",
                    command_id="python_build",
                    available=importlib.util.find_spec("build") is not None,
                    source="pyproject.toml",
                )
            )
        scripts = package_data(root).get("scripts", {})
        for kind, script in [
            ("lint", "lint"),
            ("type", "typecheck"),
            ("build", "build"),
            ("unit", "test"),
            ("integration", "test:integration"),
            ("regression", "test:regression"),
        ]:
            if script in scripts:
                capabilities.append(
                    Capability(
                        kind=kind,
                        command_id="npm_" + kind,
                        available=bool(shutil.which("node")) and npm_cli() is not None,
                        source="package.json:scripts:" + script,
                    )
                )
        if (root / "requirements.txt").exists():
            capabilities.append(
                Capability(
                    kind="security_dependency_scan",
                    command_id="pip_audit",
                    available=importlib.util.find_spec("pip_audit") is not None,
                    source="requirements.txt",
                )
            )
    if project.api_endpoints:
        for kind in ("api", "smoke", "security_headers"):
            if kind == "security_headers" or any(kind in e.tags for e in project.api_endpoints):
                capabilities.append(Capability(kind=kind, available=True, source="project.api_endpoints"))
    if project.journeys:
        available = bool(shutil.which("node")) and (worker_root() / "node_modules/@playwright/test/cli.js").is_file()
        for kind in ("browser_e2e", "accessibility", "web_diagnostics"):
            capabilities.append(
                Capability(
                    kind=kind, available=available, source="project.journeys", reason="" if available else "BROWSER_WORKER_UNAVAILABLE"
                )
            )
    return capabilities


def worker_root():
    return Path(__file__).resolve().parent.parent / "browser_worker"


def npm_cli():
    node = shutil.which("node")
    if node:
        candidates = [
            Path(node).parent / "node_modules/npm/bin/npm-cli.js",
            Path(node).parent.parent / "lib/node_modules/npm/bin/npm-cli.js",
        ]
        npm = shutil.which("npm")
        if npm:
            resolved = Path(npm).resolve()
            if resolved.name == "npm-cli.js":
                candidates.append(resolved)
        return next((str(p) for p in candidates if p.is_file()), None)
    return None


def command_argv(command_id):
    commands = {
        "pytest_unit": [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-m", "not integration and not regression"],
        "pytest_integration": [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-m", "integration"],
        "pytest_regression": [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-m", "regression"],
        "ruff": [sys.executable, "-m", "ruff", "check", "."],
        "mypy": [sys.executable, "-m", "mypy", "."],
        "python_build": [sys.executable, "-m", "build", "--no-isolation"],
        "pip_audit": [sys.executable, "-m", "pip_audit", "-r", "requirements.txt", "--no-deps", "--disable-pip", "--format", "json"],
    }
    for kind, script in [
        ("lint", "lint"),
        ("type", "typecheck"),
        ("build", "build"),
        ("unit", "test"),
        ("integration", "test:integration"),
        ("regression", "test:regression"),
    ]:
        commands["npm_" + kind] = [shutil.which("node") or "node", npm_cli() or "MISSING_NPM", "run", script, "--ignore-scripts"]
    if command_id not in commands:
        raise PolicyBlocked("UNKNOWN_COMMAND_ID")
    return commands[command_id]
