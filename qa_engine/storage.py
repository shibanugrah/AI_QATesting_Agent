from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from qa_engine.domain import MemoryRecord, Project, RunResult, now
from qa_engine.security import PolicyBlocked, Redactor, digest
from qa_engine.stages import TRANSITIONS


class Store:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "qa.sqlite3"
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version > 1:
                raise RuntimeError("DATABASE_VERSION_NEWER_THAN_ENGINE")
            if version < 1:
                sql = (Path(__file__).parent / "migrations/001_initial.sql").read_text()
                db.executescript("BEGIN IMMEDIATE;\n" + sql + "\nPRAGMA user_version=1;\nCOMMIT;")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def enroll(self, project: Project):
        # Owner action, never implicit during a verification run.
        with self.connect() as db:
            previous = db.execute("SELECT config_hash FROM projects WHERE id=?", (project.id,)).fetchone()
            db.execute(
                "INSERT INTO projects VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET config=excluded.config, config_hash=excluded.config_hash, enrolled_at=excluded.enrolled_at",
                (project.id, project.model_dump_json(), digest(project), now()),
            )
            if project.repository:
                db.execute(
                    "INSERT INTO repositories VALUES(?,?) ON CONFLICT(project_id) DO UPDATE SET path=excluded.path",
                    (project.id, project.repository),
                )
            db.execute("INSERT OR IGNORE INTO environments VALUES(?,?)", (project.id, project.environment))
            if previous and previous[0] != digest(project):
                for row in db.execute(
                    "SELECT record FROM memory_records WHERE project_id=? AND state='APPROVED'", (project.id,)
                ).fetchall():
                    record = MemoryRecord.model_validate_json(row[0])
                    record.state = "STALE"
                    db.execute("UPDATE memory_records SET state=?,record=? WHERE id=?", (record.state, record.model_dump_json(), record.id))

    def project(self, project_id: str) -> Project:
        with self.connect() as db:
            row = db.execute("SELECT config,config_hash FROM projects WHERE id=?", (project_id,)).fetchone()
        if not row:
            raise PolicyBlocked("PROJECT_NOT_ENROLLED")
        project = Project.model_validate_json(row[0])
        if digest(project) != row[1]:
            raise PolicyBlocked("PROJECT_POLICY_INTEGRITY_ERROR")
        return project

    def save_run(self, run: RunResult, redactor: Redactor):
        data = redactor.clean(run.model_dump(mode="json"))
        encoded = json.dumps(data, sort_keys=True)
        with self.connect() as db:
            db.execute(
                "INSERT INTO runs VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET status=excluded.status,result=excluded.result,result_hash=excluded.result_hash",
                (run.run_id, run.project_id, run.run_status, encoded, hashlib.sha256(encoded.encode()).hexdigest()),
            )
            for stage in data["stages"]:
                db.execute(
                    "INSERT OR REPLACE INTO stages VALUES(?,?,?,?)", (run.project_id, run.run_id, stage["stage_id"], json.dumps(stage))
                )
            for check in data["checks"]:
                db.execute(
                    "INSERT INTO checks VALUES(?,?,?,?) ON CONFLICT(run_id,check_id) DO UPDATE SET record=excluded.record",
                    (run.project_id, run.run_id, check["id"], json.dumps(check)),
                )
                for attempt in check["attempts"]:
                    db.execute(
                        "INSERT OR REPLACE INTO attempts VALUES(?,?,?,?,?)",
                        (run.project_id, run.run_id, check["id"], attempt["number"], json.dumps(attempt)),
                    )
            for artifact in data["artifacts"]:
                db.execute(
                    "INSERT OR REPLACE INTO artifacts VALUES(?,?,?,?)", (artifact["id"], run.project_id, run.run_id, json.dumps(artifact))
                )
            for finding in data["findings"]:
                encoded_finding = json.dumps(finding, sort_keys=True)
                if not db.execute("SELECT 1 FROM findings WHERE run_id=? AND record=?", (run.run_id, encoded_finding)).fetchone():
                    db.execute(
                        "INSERT INTO findings(project_id,run_id,record) VALUES(?,?,?)", (run.project_id, run.run_id, encoded_finding)
                    )

    def transition(self, run, stage_id, status, redactor, reason=None):
        stage = run.stages[stage_id - 1]
        if status not in TRANSITIONS.get(stage.status, set()):
            raise ValueError(f"INVALID_STAGE_TRANSITION:{stage.status}:{status}")
        stage.status = status
        if status == "RUNNING":
            stage.started_at = now()
            stage.attempts += 1
        if status in {"SUCCEEDED", "FAILED", "ERROR", "BLOCKED", "SKIPPED", "CANCELLED"}:
            stage.finished_at = now()
        if status == "SKIPPED":
            stage.skip_reason = reason
        elif reason:
            stage.failure_code = reason
            stage.failure_effect = "prevents_clean_pass"
        self.save_run(run, redactor)
        with self.connect() as db:
            db.execute(
                "INSERT INTO events(project_id,run_id,stage_id,at,status) VALUES(?,?,?,?,?)",
                (run.project_id, run.run_id, stage_id, now(), status),
            )

    def get_run(self, project_id: str, run_id: str) -> RunResult:
        with self.connect() as db:
            row = db.execute("SELECT result,result_hash FROM runs WHERE project_id=? AND id=?", (project_id, run_id)).fetchone()
        if not row:
            raise KeyError("RUN_NOT_FOUND_IN_PROJECT")
        if hashlib.sha256(row[0].encode()).hexdigest() != row[1]:
            raise PolicyBlocked("RUN_INTEGRITY_ERROR")
        return RunResult.model_validate_json(row[0])

    def register_artifacts(self, run, artifacts):
        with self.connect() as db:
            for artifact in artifacts:
                db.execute("INSERT INTO artifacts VALUES(?,?,?,?)", (artifact.id, run.project_id, run.run_id, artifact.model_dump_json()))

    def artifact_records(self, project_id, run_id):
        from qa_engine.domain import ArtifactRef

        with self.connect() as db:
            rows = db.execute("SELECT record FROM artifacts WHERE project_id=? AND run_id=?", (project_id, run_id)).fetchall()
        return [ArtifactRef.model_validate_json(row[0]) for row in rows]

    def save_memory(self, record: MemoryRecord, redactor: Redactor):
        record = MemoryRecord.model_validate(redactor.clean(record.model_dump()))
        with self.connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO incidents VALUES(?,?,?,?,?)",
                (record.id, record.project_id, record.run_id, record.check_id, record.fingerprint),
            )
            db.execute(
                "INSERT INTO memory_records VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET state=excluded.state,record=excluded.record,expires_at=excluded.expires_at",
                (record.id, record.project_id, record.state, record.policy_hash, record.expires_at, record.model_dump_json()),
            )
            db.execute("DELETE FROM memory_fts WHERE memory_id=?", (record.id,))
            db.execute("INSERT INTO memory_fts VALUES(?,?,?)", (record.id, record.project_id, record.text))

    def get_memory(self, project_id, memory_id):
        with self.connect() as db:
            row = db.execute("SELECT record FROM memory_records WHERE project_id=? AND id=?", (project_id, memory_id)).fetchone()
        if not row:
            raise KeyError("MEMORY_NOT_FOUND_IN_PROJECT")
        return MemoryRecord.model_validate_json(row[0])

    def search(self, project_id: str, query: str):
        import re

        terms = re.findall(r"[\w]+", query)[:20]
        if not terms:
            return []
        expression = " OR ".join('"' + word + '"' for word in terms)
        policy_hash = digest(self.project(project_id))
        with self.connect() as db:
            rows = db.execute(
                "SELECT m.record FROM memory_fts f JOIN memory_records m ON m.id=f.memory_id WHERE memory_fts MATCH ? AND m.project_id=? AND f.project_id=? AND m.state='APPROVED' AND m.expires_at>? AND m.policy_hash=? AND EXISTS (SELECT 1 FROM reviews r WHERE r.project_id=m.project_id AND r.subject_id=m.id AND r.decision='APPROVED') ORDER BY rank LIMIT 10",
                (expression, project_id, project_id, now(), policy_hash),
            ).fetchall()
        return [MemoryRecord.model_validate_json(row[0]) for row in rows]
