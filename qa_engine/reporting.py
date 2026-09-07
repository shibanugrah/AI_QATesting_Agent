from html import escape


def markdown(run):
    repo = run.plan.repository
    lines = [
        f"# QA Engine — {run.gate.decision}",
        "",
        f"Run: `{run.run_id}` · Project: `{run.project_id}` · Environment: `{run.environment_id}`",
        f"Run status: **{run.run_status}** · Report review: **{run.approval}**",
        "",
        "Reason codes: " + ", ".join(run.gate.reason_codes),
        "",
    ]
    if repo:
        lines += [
            f"Head: `{repo.head_sha}`",
            f"Base: `{repo.base_sha or 'not provided'}`",
            f"Dirty workspace: `{repo.dirty}` · hash: `{repo.dirty_diff_hash}`",
            f"Changed files: {len(repo.changed_files)}",
            "",
        ]
    lines += ["| Check | Mandatory | Status | Classification / reason | Attempts |", "|---|---|---|---|---|"]
    for c in run.checks:
        lines.append(f"| {c.id} | {c.mandatory} | {c.status} | {c.classification}: {c.reason} | {len(c.attempts)} |")
    if run.previous_run_id:
        lines += ["", f"Original failure run: `{run.previous_run_id}`"]
    lines += ["", "## Observable checkpoints", "", "| # | Checkpoint | Status | Reason |", "|---|---|---|---|"]
    for s in run.stages:
        lines.append(f"| {s.stage_id} | {s.name} | {s.status} | {s.skip_reason or s.failure_code or ''} |")
    lines += ["", "## Evidence", ""]
    for a in run.artifacts:
        lines.append(f"- `{a.path}` · SHA-256 `{a.sha256}` · {a.size} bytes")
    lines += [
        "",
        "Automated accessibility results cover configured axe rules only. No AI claims are used as evidence.",
        "Local reports are pending human review before export. Controlled fixtures do not establish external pilot validation.",
    ]
    return "\n".join(lines) + "\n"


def html(run):
    return (
        '<!doctype html><html lang="en"><meta charset="utf-8"><title>QA Engine report</title><body><pre>'
        + escape(markdown(run))
        + "</pre></body></html>"
    )
