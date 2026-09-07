from qa_engine.domain import GateResult
from qa_engine.evidence import Evidence


def evaluate(run, root):
    if run.plan.request.dry_run:
        return GateResult(reason_codes=["DRY_RUN"])
    if run.run_status in {"RUNNING", "ERROR", "CANCELLED"}:
        return GateResult(reason_codes=["RUN_NOT_COMPLETED"])
    if any(not Evidence.verify(root, a, run.project_id, run.run_id) for a in run.artifacts):
        return GateResult(decision="REVIEW_REQUIRED", reason_codes=["EVIDENCE_INTEGRITY_FAILURE"])
    if any(c.status == "FAILED" and c.classification != "FLAKY_SUSPECTED" for c in run.checks):
        return GateResult(decision="FAIL", reason_codes=["CONFIRMED_CHECK_FAILURE"])
    missing = []
    for item in run.plan.items:
        if not item.mandatory:
            continue
        check = next((c for c in run.checks if c.id == item.id), None)
        if (
            not check
            or check.status != "SUCCEEDED"
            or not check.attempts
            or any(a.status != "SUCCEEDED" or not a.evidence for a in check.attempts)
        ):
            missing.append(item.id)
    for kind in run.plan.required:
        if not any(i.kind == kind and i.mandatory for i in run.plan.items):
            missing.append(kind)
    reasons = []
    if missing:
        reasons.append("MANDATORY_CHECK_NOT_EXECUTED_SUCCESSFULLY")
    if any(c.classification == "FLAKY_SUSPECTED" for c in run.checks):
        reasons.append("FLAKY_SUSPECTED")
    if any(c.status in {"ERROR", "BLOCKED"} for c in run.checks):
        reasons.append("CHECK_BLOCKED_OR_ERRORED")
    if run.run_status != "COMPLETED":
        reasons.append("RUN_INCOMPLETE")
    if any(s.status in {"FAILED", "BLOCKED", "ERROR", "CANCELLED", "RUNNING", "PENDING", "READY"} for s in run.stages if s.stage_id < 29):
        reasons.append("STAGE_INCOMPLETE_OR_FAILED")
    if not run.plan.required or not run.checks:
        reasons.append("NO_VERIFICATION_FLOOR")
    if run.operation == "VERIFY_FIX" and not run.previous_run_id:
        reasons.append("ORIGINAL_FAILURE_NOT_LINKED")
    if reasons:
        return GateResult(decision="REVIEW_REQUIRED", reason_codes=reasons, missing=missing)
    return GateResult(decision="PASS", reason_codes=["ALL_MANDATORY_CHECKS_EXECUTED_SUCCESSFULLY"])
