from __future__ import annotations

import json
import platform
from datetime import datetime, timedelta, timezone
from pathlib import Path

from qa_engine import __version__
from qa_engine.domain import CheckResult, Finding, GateResult, MemoryRecord, Project, RunRequest, RunResult, StageResult, now
from qa_engine.evidence import Evidence
from qa_engine.executors import Executors
from qa_engine.gate import evaluate
from qa_engine.planning import build_plan, definition
from qa_engine.reporting import html, markdown
from qa_engine.repository import snapshot
from qa_engine.security import PolicyBlocked, Redactor, SafeHTTP, SecretProvider, URLGuard, digest, fingerprint
from qa_engine.stages import CHECK_STAGE, NAMES
from qa_engine.storage import Store


class Engine:
    """Stable local API. Enrollment/review are explicit owner operations."""

    def __init__(self, data_dir=".qa-engine"):
        self.store = Store(data_dir)

    def enroll(self, project: Project):
        project = Project.model_validate(project.model_dump())
        encoded = project.model_dump_json()
        if any(value and value in encoded for value in SecretProvider(project).available().values()):
            raise PolicyBlocked("INLINE_SECRET_IN_CONFIGURATION")
        if project.repository:
            project.repository = str(Path(project.repository).resolve(strict=True))
        for endpoint in project.api_endpoints:
            URLGuard(project).parse(endpoint.url)
        for journey in project.journeys:
            for step in journey.steps:
                if step.action == "goto":
                    URLGuard(project).parse(step.value)
        self.store.enroll(project)
        return project

    def plan(self, request: RunRequest):
        request = RunRequest.model_validate(request.model_dump())
        project = self.store.project(request.project_id)
        plan = build_plan(project, request, snapshot_enabled=not request.dry_run)
        redactor = Redactor(SecretProvider(project).available().values())
        return type(plan).model_validate(redactor.clean(plan.model_dump()))

    def verify_change(self, project_id, **kwargs):
        return self.run(RunRequest(project_id=project_id, operation="VERIFY_CHANGE", **kwargs))

    def verify_fix(self, project_id, previous_run_id, **kwargs):
        return self.run(RunRequest(project_id=project_id, operation="VERIFY_FIX", previous_run_id=previous_run_id, **kwargs))

    def run(self, request: RunRequest):
        request = RunRequest.model_validate(request.model_dump())
        project = self.store.project(request.project_id)
        secrets = SecretProvider(project)
        redactor = Redactor(secrets.available().values())
        # Construct and persist intake before live repository/network/process work.
        plan = build_plan(project, request, snapshot_enabled=False)
        run = RunResult(
            project_id=project.id,
            environment_id=project.environment,
            operation=request.operation,
            plan=plan,
            previous_run_id=request.previous_run_id,
            stages=[
                StageResult(
                    stage_id=i + 1,
                    name=name,
                    policy_version=project.policy.version,
                    timeout=project.policy.timeout_seconds,
                    retry_policy=project.policy.diagnostic_retries,
                )
                for i, name in enumerate(NAMES)
            ],
            tool_versions={"qa_engine": __version__, "python": platform.python_version()},
        )
        evidence = Evidence(self.store.root, project, run.run_id, redactor)
        self.store.save_run(run, redactor)
        active = []

        def start(*ids):
            for stage_id in ids:
                self.store.transition(run, stage_id, "READY", redactor)
                self.store.transition(run, stage_id, "RUNNING", redactor)
                active.append(stage_id)

        def finish(*ids, status="SUCCEEDED", reason=None):
            for stage_id in ids:
                self.store.transition(run, stage_id, status, redactor, reason)
                if stage_id in active:
                    active.remove(stage_id)

        try:
            start(1, 2, 3)
            finish(1, 2, 3)
            start(7)
            # Caller context is inert text, never evidence or policy.
            finish(7)
            planning_stages = [9, 11, 12, 13, 14]
            if request.dry_run or not project.repository:
                for stage_id in (6, 8):
                    self.store.transition(run, stage_id, "SKIPPED", redactor, "DRY_RUN" if request.dry_run else "NO_REPOSITORY_TARGET")
            else:
                planning_stages = [6, 8] + planning_stages
            start(*planning_stages)
            run.plan = self.plan(request)
            if run.operation == "VERIFY_FIX":
                self._fix_plan(project, run)
            finish(*planning_stages)
            start(10)
            run.memory_matches = [m.id for m in self.find_incidents(project.id, redactor.text(request.context))]
            finish(10)
            if request.dry_run:
                for stage_id in (4, 5):
                    self.store.transition(run, stage_id, "SKIPPED", redactor, "DRY_RUN")
            else:
                start(4, 5)
                for item in run.plan.items:
                    if not item.available:
                        continue
                    if item.kind in {"api", "smoke", "security_headers"}:
                        endpoints = (
                            project.api_endpoints
                            if item.kind == "security_headers"
                            else [next(e for e in project.api_endpoints if item.id == item.kind + "-" + e.id)]
                        )
                        for endpoint in endpoints:
                            if endpoint.credential_ref:
                                secrets.resolve(endpoint.credential_ref)
                            URLGuard(project).resolve(endpoint.url)
                    elif item.kind in {"browser_e2e", "accessibility", "web_diagnostics"}:
                        journey = next(j for j in project.journeys if item.id == item.kind + "-" + j.id)
                        for step in journey.steps:
                            if step.credential_ref:
                                secrets.resolve(step.credential_ref)
                            if step.action == "goto":
                                URLGuard(project).resolve(step.value)
                finish(4, 5)
            start(15)
            if digest(self.store.project(project.id)) != run.plan.policy_hash:
                raise PolicyBlocked("POLICY_CHANGED_DURING_PLANNING")
            finish(15)
            if request.dry_run:
                for item in run.plan.items:
                    run.checks.append(CheckResult(id=item.id, kind=item.kind, mandatory=item.mandatory, status="SKIPPED", reason="DRY_RUN"))
                for stage in run.stages[15:28]:
                    if stage.status == "PENDING":
                        self.store.transition(
                            run, stage.stage_id, "SKIPPED", redactor, "DRY_RUN" if stage.stage_id != 23 else "CAPABILITY_NOT_IN_V1_POLICY"
                        )
            else:
                executor = Executors(project, SafeHTTP(project), secrets, evidence)
                # Execution nodes are grouped by capability; telemetry maps multiple checks to a stage.
                for stage_id in range(16, 26):
                    items = [i for i in run.plan.items if CHECK_STAGE[i.kind] == stage_id]
                    if not items:
                        self.store.transition(
                            run, stage_id, "SKIPPED", redactor, "CAPABILITY_NOT_IN_V1_POLICY" if stage_id == 23 else "NOT_IN_PROJECT_PLAN"
                        )
                        continue
                    start(stage_id)
                    for item in items:
                        check = CheckResult(
                            id=item.id,
                            kind=item.kind,
                            mandatory=item.mandatory,
                            status="RUNNING" if item.available else "BLOCKED",
                            reason=item.reason,
                            definition_hash=definition(project, item) if item.available else "",
                        )
                        run.checks.append(check)
                        self.store.save_run(run, redactor)
                        if not item.available:
                            check.classification = "POLICY_BLOCKED"
                            continue
                        for number in range(1, project.policy.diagnostic_retries + 2):
                            attempt = executor.run(item, number)
                            check.attempts.append(attempt)
                            run.artifacts.extend(attempt.evidence)
                            self.store.save_run(run, redactor)
                            if attempt.status in {"SUCCEEDED", "BLOCKED"}:
                                break
                            if attempt.status == "FAILED" and number >= 2:
                                break  # One diagnostic assertion rerun; infrastructure may use two.
                        self._classify(check, redactor)
                    current = [c for c in run.checks if CHECK_STAGE[c.kind] == stage_id]
                    failed = any(c.status == "FAILED" for c in current)
                    incomplete = any(c.status in {"ERROR", "BLOCKED"} for c in current)
                    stage = run.stages[stage_id - 1]
                    stage.output_refs = [c.id for c in current]
                    stage.evidence_refs = [a.id for c in current for attempt in c.attempts for a in attempt.evidence]
                    finish(
                        stage_id,
                        status="FAILED" if failed else "BLOCKED" if incomplete else "SUCCEEDED",
                        reason="CHECK_FAILURE" if failed else "CHECK_INCOMPLETE" if incomplete else None,
                    )
                start(26)
                if not all(Evidence.verify(self.store.root, a, run.project_id, run.run_id) for a in run.artifacts):
                    raise PolicyBlocked("EVIDENCE_INTEGRITY_FAILURE")
                if project.repository:
                    after = snapshot(project.repository, request.base_ref, request.head_ref)
                    before = run.plan.repository
                    if (after.head_sha, after.dirty_diff_hash) != (before.head_sha, before.dirty_diff_hash):
                        raise PolicyBlocked("WORKSPACE_CHANGED_DURING_VERIFICATION")
                finish(26)
                start(27)
                for c in run.checks:
                    if c.status != "SUCCEEDED":
                        run.findings.append(
                            Finding(
                                check_id=c.id,
                                category=c.classification,
                                message=c.reason,
                                evidence_refs=[a.id for attempt in c.attempts for a in attempt.evidence],
                            )
                        )
                finish(27)
                if run.operation == "VERIFY_FIX":
                    start(28)
                    self._validate_fix(project, run)
                    finish(28)
                else:
                    self.store.transition(run, 28, "SKIPPED", redactor, "NOT_A_FIX_VERIFICATION")
            run.run_status = "COMPLETED"
            start(29)
            run.gate = evaluate(run, self.store.root)
            self._observe(project, run, redactor)
            finish(29)
        except BaseException as exc:
            run.findings.append(
                Finding(check_id="engine", category="ENGINE_ERROR", message=redactor.text(type(exc).__name__ + ": " + str(exc)))
            )
            if isinstance(exc, (SystemExit, KeyboardInterrupt)):
                run.run_status = "CANCELLED"
            elif isinstance(exc, PolicyBlocked):
                run.run_status = "BLOCKED"
            else:
                run.run_status = "ERROR"
            code = redactor.text(str(exc)) if isinstance(exc, PolicyBlocked) else type(exc).__name__
            for stage_id in list(active):
                finish(
                    stage_id,
                    status="CANCELLED" if run.run_status == "CANCELLED" else "BLOCKED" if run.run_status == "BLOCKED" else "ERROR",
                    reason=code,
                )
            for stage in run.stages[:29]:
                if stage.status == "PENDING":
                    self.store.transition(run, stage.stage_id, "BLOCKED", redactor, "DEPENDENCY_NOT_COMPLETED")
            run.gate = GateResult(decision="REVIEW_REQUIRED" if run.run_status == "BLOCKED" else "NOT_EVALUATED", reason_codes=[code])
            self.store.save_run(run, redactor)
        run.finished_at = now()
        # Report generation is observable and cannot turn an incomplete execution into PASS.
        try:
            start(30)
            run.artifacts.append(evidence.retain("report.md", markdown(run), "report"))
            run.artifacts.append(evidence.retain("report.html", html(run), "report"))
            finish(30)
            self.store.save_run(run, redactor)
            # Canonical JSON includes final checkpoint state; DB additionally seals its own copy.
            canonical = evidence.retain("result.json", run.model_dump(mode="json"), "canonical_result")
            manifest = evidence.retain(
                "manifest.json",
                {"schema_version": 1, "run_id": run.run_id, "artifacts": [a.model_dump() for a in run.artifacts + [canonical]]},
                "manifest",
            )
            self.store.register_artifacts(run, [canonical, manifest])
        except Exception as exc:
            run.findings.append(
                Finding(check_id="report", category="ENGINE_ERROR", message=redactor.text(type(exc).__name__ + ": " + str(exc)))
            )
            run.run_status = "ERROR"
            run.gate = GateResult(reason_codes=["REPORT_SEALING_ERROR"])
            if run.stages[29].status == "RUNNING":
                finish(30, status="ERROR", reason="REPORT_SEALING_ERROR")
            self.store.save_run(run, redactor)
        return self.store.get_run(project.id, run.run_id)

    @staticmethod
    def _classify(check, redactor):
        statuses = [a.status for a in check.attempts]
        first = check.attempts[0]
        check.status = first.status
        check.reason = first.failure_code or ""
        if first.status != "SUCCEEDED" and "SUCCEEDED" in statuses:
            check.classification = "FLAKY_SUSPECTED"
            check.status = "FAILED"
        elif first.status == "BLOCKED":
            check.classification = "POLICY_BLOCKED"
        elif first.status == "ERROR":
            check.classification = "INFRASTRUCTURE_ERROR"
        elif first.status == "FAILED":
            check.classification = "PRODUCT_REGRESSION"
        else:
            check.classification = "NONE"
        if first.status != "SUCCEEDED":
            check.fingerprint = fingerprint(
                check.id, check.kind, first.failure_code or "", json.dumps(first.details, sort_keys=True), redactor
            )

    def _fix_plan(self, project, run):
        if not run.previous_run_id:
            raise PolicyBlocked("PREVIOUS_RUN_REQUIRED")
        previous = self.store.get_run(project.id, run.previous_run_id)
        if previous.gate.decision != "FAIL" or not self._intact(previous):
            raise PolicyBlocked("ORIGINAL_FAILURE_NOT_CONFIRMED")
        failures = [c for c in previous.checks if c.status == "FAILED" and c.classification == "PRODUCT_REGRESSION"]
        if not failures:
            raise PolicyBlocked("NO_ORIGINAL_FAILING_CHECK")
        request = run.plan.request.model_copy(deep=True)
        request.profiles = sorted(
            set(request.profiles) | {c.kind for c in failures} | set(project.policy.regression_checks) | set(project.policy.required)
        )
        run.plan = build_plan(project, request, snapshot_enabled=not request.dry_run)
        mandatory_kinds = set(run.plan.required) | set(project.policy.regression_checks) | {c.kind for c in failures}
        run.plan.required = sorted(mandatory_kinds)
        for item in run.plan.items:
            if item.kind in mandatory_kinds:
                item.mandatory = True
        for failure in failures:
            item = next((i for i in run.plan.items if i.id == failure.id and i.available), None)
            if not item or definition(project, item) != failure.definition_hash:
                raise PolicyBlocked("ORIGINAL_CHECK_MISSING_OR_CHANGED")

    def _validate_fix(self, project, run):
        previous = self.store.get_run(project.id, run.previous_run_id)
        original = [c for c in previous.checks if c.status == "FAILED" and c.classification == "PRODUCT_REGRESSION"]
        if not all(
            any(
                c.id == old.id and c.status == "SUCCEEDED" and c.attempts and all(a.status == "SUCCEEDED" for a in c.attempts)
                for c in run.checks
            )
            for old in original
        ):
            raise PolicyBlocked("ORIGINAL_FAILURE_STILL_PRESENT")
        for old in original:
            new = next(c for c in run.checks if c.id == old.id)
            for test in old.attempts[0].details.get("test_cases", []):
                if test["failed"]:
                    candidate = next((t for t in new.attempts[0].details.get("test_cases", []) if t["id"] == test["id"]), None)
                    if (
                        not candidate
                        or candidate["failed"]
                        or candidate["skipped"]
                        or not test["source_hash"]
                        or candidate["source_hash"] != test["source_hash"]
                    ):
                        raise PolicyBlocked("ORIGINAL_TEST_REMOVED_CHANGED_OR_SKIPPED")
        if not all(any(c.kind == kind and c.status == "SUCCEEDED" for c in run.checks) for kind in project.policy.regression_checks):
            raise PolicyBlocked("REQUIRED_REGRESSION_NOT_SUCCESSFUL")

    def _observe(self, project, run, redactor):
        expiry = (datetime.now(timezone.utc) + timedelta(days=project.policy.retention_days)).isoformat()
        for check in run.checks:
            if check.classification == "PRODUCT_REGRESSION" and check.fingerprint:
                record = MemoryRecord(
                    project_id=project.id,
                    run_id=run.run_id,
                    check_id=check.id,
                    fingerprint=check.fingerprint,
                    text=f"{check.id} {check.reason} {check.fingerprint}",
                    policy_hash=run.plan.policy_hash,
                    expires_at=expiry,
                    state="REPRODUCED" if len(check.attempts) >= 2 and all(a.status == "FAILED" for a in check.attempts) else "OBSERVED",
                )
                self.store.save_memory(record, redactor)
        if run.operation == "VERIFY_FIX" and run.gate.decision == "PASS":
            with self.store.connect() as db:
                rows = db.execute("SELECT record FROM memory_records WHERE project_id=? AND state='REPRODUCED'", (project.id,)).fetchall()
            for row in rows:
                record = MemoryRecord.model_validate_json(row[0])
                if record.run_id == run.previous_run_id and record.policy_hash == run.plan.policy_hash:
                    record.state, record.fix_run_id = "FIX_VALIDATED", run.run_id
                    self.store.save_memory(record, redactor)

    def _intact(self, run):
        artifacts = self.store.artifact_records(run.project_id, run.run_id)
        return bool(artifacts) and all(Evidence.verify(self.store.root, a, run.project_id, run.run_id) for a in artifacts)

    def get_run(self, project_id, run_id):
        return self.store.get_run(project_id, run_id)

    def gate(self, project_id, run_id):
        run = self.get_run(project_id, run_id)
        if not self._intact(run):
            return GateResult(decision="REVIEW_REQUIRED", reason_codes=["EVIDENCE_INTEGRITY_FAILURE"])
        if digest(self.store.project(project_id)) != run.plan.policy_hash:
            return GateResult(decision="REVIEW_REQUIRED", reason_codes=["PROJECT_POLICY_CHANGED_REVERIFY"])
        return evaluate(run, self.store.root)

    def find_incidents(self, project_id, query):
        trusted = []
        for record in self.store.search(project_id, query):
            try:
                original = self.get_run(project_id, record.run_id)
                fix = self.get_run(project_id, record.fix_run_id)
                check = next((c for c in original.checks if c.id == record.check_id), None)
                if (
                    check
                    and check.classification == "PRODUCT_REGRESSION"
                    and len(check.attempts) >= 2
                    and all(a.status == "FAILED" for a in check.attempts)
                    and fix.previous_run_id == original.run_id
                    and self._intact(original)
                    and self._intact(fix)
                    and self.gate(project_id, fix.run_id).decision == "PASS"
                ):
                    trusted.append(record)
            except (KeyError, PolicyBlocked):
                continue
        return trusted

    def review_memory(self, project_id, record_id, decision, *, reviewer):
        if decision not in {"APPROVED", "REJECTED", "STALE", "EXPIRED"} or not reviewer.strip():
            raise ValueError("EXPLICIT_HUMAN_REVIEW_REQUIRED")
        record = self.store.get_memory(project_id, record_id)
        project = self.store.project(project_id)
        if decision == "APPROVED":
            if (
                record.state != "FIX_VALIDATED"
                or not record.sanitized
                or record.expires_at <= now()
                or record.policy_hash != digest(project)
                or not record.fix_run_id
            ):
                raise PolicyBlocked("MEMORY_NOT_ELIGIBLE_FOR_APPROVAL")
            original = self.get_run(project_id, record.run_id)
            fix = self.get_run(project_id, record.fix_run_id)
            check = next(c for c in original.checks if c.id == record.check_id)
            if (
                len(check.attempts) < 2
                or not all(a.status == "FAILED" for a in check.attempts)
                or not self._intact(original)
                or not self._intact(fix)
                or self.gate(project_id, fix.run_id).decision != "PASS"
                or fix.previous_run_id != original.run_id
            ):
                raise PolicyBlocked("MEMORY_EVIDENCE_NOT_VALID")
        redactor = Redactor(SecretProvider(project).available().values())
        record.state = decision
        self.store.save_memory(record, redactor)
        with self.store.connect() as db:
            db.execute(
                "INSERT INTO reviews(project_id,subject_id,decision,reviewer,at) VALUES(?,?,?,?,?)",
                (project_id, record_id, decision, redactor.text(reviewer), now()),
            )
        return record

    def review_report(self, project_id, run_id, decision, *, reviewer):
        if decision not in {"APPROVED", "REJECTED"} or not reviewer.strip():
            raise ValueError("EXPLICIT_HUMAN_REVIEW_REQUIRED")
        run = self.get_run(project_id, run_id)
        if not self._intact(run):
            raise PolicyBlocked("EVIDENCE_INTEGRITY_FAILURE")
        run.approval = decision
        redactor = Redactor(SecretProvider(self.store.project(project_id)).available().values())
        self.store.save_run(run, redactor)
        with self.store.connect() as db:
            db.execute(
                "INSERT INTO reviews(project_id,subject_id,decision,reviewer,at) VALUES(?,?,?,?,?)",
                (project_id, run_id, decision, redactor.text(reviewer), now()),
            )
        return run

    def export_report(self, project_id, run_id, destination):
        run = self.get_run(project_id, run_id)
        if run.approval != "APPROVED":
            raise PolicyBlocked("HUMAN_APPROVAL_REQUIRED")
        if not self._intact(run):
            raise PolicyBlocked("EVIDENCE_INTEGRITY_FAILURE")
        with Path(destination).open("x", encoding="utf-8") as out:
            out.write(markdown(run))
        return str(Path(destination).resolve())
