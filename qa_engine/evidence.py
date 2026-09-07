from __future__ import annotations

import hashlib
import json
from pathlib import Path

from qa_engine.domain import ArtifactRef
from qa_engine.security import BudgetExceeded


class Evidence:
    def __init__(self, root, project, run_id, redactor):
        self.root = Path(root).resolve()
        self.directory = self.root / "projects" / project.id / "runs" / run_id
        self.directory.mkdir(parents=True, exist_ok=True)
        if not self.directory.resolve().is_relative_to(self.root):
            raise ValueError("ARTIFACT_NAMESPACE_ESCAPE")
        self.project, self.redactor = project, redactor

    def retain(self, name, value, kind="json"):
        if Path(name).name != name:
            raise ValueError("INVALID_ARTIFACT_NAME")
        if isinstance(value, bytes):
            data = value  # Only validated browser media may use this path.
        elif isinstance(value, str):
            data = self.redactor.text(value).encode()
        else:
            data = json.dumps(self.redactor.clean(value), sort_keys=True, indent=2).encode()
        if len(data) > self.project.policy.max_artifact_bytes:
            raise BudgetExceeded("ARTIFACT_SIZE_EXCEEDED")
        if sum(p.stat().st_size for p in self.directory.iterdir() if p.is_file()) + len(data) > self.project.policy.max_run_artifact_bytes:
            raise BudgetExceeded("RUN_ARTIFACT_BUDGET_EXCEEDED")
        path = self.directory / name
        with path.open("xb") as f:
            f.write(data)
        return ArtifactRef(
            path=str(path.relative_to(self.root)),
            sha256=hashlib.sha256(data).hexdigest(),
            size=len(data),
            kind=kind,
            retention_days=self.project.policy.retention_days,
        )

    @staticmethod
    def verify(root, artifact, project_id=None, run_id=None):
        root = Path(root).resolve()
        path = (root / artifact.path).resolve()
        namespace = root / "projects" / project_id / "runs" / run_id if project_id and run_id else root
        return (
            path.is_relative_to(namespace)
            and path.is_file()
            and path.stat().st_size == artifact.size
            and hashlib.sha256(path.read_bytes()).hexdigest() == artifact.sha256
        )
