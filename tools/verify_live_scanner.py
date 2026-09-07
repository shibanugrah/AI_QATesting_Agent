"""Read-only live pip-audit adapter verification against a controlled vulnerable requirement."""

import json
from pathlib import Path
from uuid import uuid4

from qa_engine import Engine
from qa_engine.domain import Policy, Project
from tests.engine_fixtures import make_repository


def main():
    output = Path("artifacts/live-scanner") / str(uuid4())
    repo = make_repository(output / "fixture")
    (repo / "requirements.txt").write_text("urllib3==1.26.5\n")
    engine = Engine(output / "data")
    project = Project(
        id="live-scanner-fixture",
        repository=str(repo.resolve()),
        policy=Policy(required=["security_dependency_scan"], allowed_commands=["pip_audit"], diagnostic_retries=0, timeout_seconds=90),
    )
    engine.enroll(project)
    result = engine.verify_change(project.id)
    vulnerabilities = [v for check in result.checks for attempt in check.attempts for v in attempt.details.get("vulnerabilities", [])]
    verified = result.gate.decision == "FAIL" and bool(vulnerabilities)
    evidence = {
        "status": "PASS" if verified else "NOT REVERIFIED",
        "run_id": result.run_id,
        "gate": result.gate.model_dump(),
        "vulnerability_count": len(vulnerabilities),
        "data_dir": str(engine.store.root),
    }
    (output / "result.json").write_text(json.dumps(evidence, indent=2))
    print(json.dumps(evidence, indent=2))
    return 0 if verified else 1


if __name__ == "__main__":
    raise SystemExit(main())
