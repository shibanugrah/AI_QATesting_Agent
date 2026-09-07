from __future__ import annotations

from fnmatch import fnmatch

from qa_engine.domain import PlanItem, TestPlan
from qa_engine.repository import discover, snapshot
from qa_engine.security import PolicyBlocked, digest
from qa_engine.github import bind_pull_request


def build_plan(project, request, *, snapshot_enabled=True):
    if request.github_pr and not project.repository:
        raise PolicyBlocked("GITHUB_METADATA_REQUIRES_REPOSITORY")
    repository = snapshot(project.repository, request.base_ref, request.head_ref) if project.repository and snapshot_enabled else None
    if repository and request.github_pr:
        pr = request.github_pr
        repository = bind_pull_request(
            repository,
            {
                "repository": {"full_name": pr.repository},
                "pull_request": {"number": pr.number, "base": {"sha": pr.base_sha}, "head": {"sha": pr.head_sha}},
            },
        )
    required = set(project.policy.required)
    for condition in project.policy.conditional:
        if repository is None or not request.base_ref or any(fnmatch(path, condition.pattern) for path in repository.changed_files):
            required.update(condition.required)
    inventory = discover(project)
    selected = (
        set(request.profiles)
        if request.profiles
        else {c.kind for c in inventory if c.available and (not c.command_id or c.command_id in project.policy.allowed_commands)} | required
    )
    selected.update(request.advisory_additions)
    items = []
    for kind in sorted(selected | required):
        candidates = [c for c in inventory if c.kind == kind]
        approved_native = [c for c in candidates if c.command_id in project.policy.allowed_commands and (c.available or kind in required)]
        if len(approved_native) > 1:
            for native in approved_native:
                reason = "PROFILE_FILTERED" if kind not in selected else "" if native.available else "CAPABILITY_UNAVAILABLE"
                items.append(
                    PlanItem(
                        id=kind + "-" + native.command_id,
                        kind=kind,
                        mandatory=kind in required,
                        available=not reason,
                        command_id=native.command_id,
                        source=native.source,
                        reason=reason,
                    )
                )
            continue
        capability = next(
            (c for c in candidates if c.available and (not c.command_id or c.command_id in project.policy.allowed_commands)),
            next(iter(candidates), None),
        )
        reason = "" if capability and capability.available else "CAPABILITY_UNAVAILABLE"
        if kind not in selected:
            reason = "PROFILE_FILTERED"
        elif capability and capability.command_id and capability.command_id not in project.policy.allowed_commands:
            reason = "COMMAND_NOT_AUTHORIZED"
        if kind in {"api", "smoke"} and capability:
            for endpoint in project.api_endpoints:
                if kind in endpoint.tags:
                    items.append(
                        PlanItem(
                            id=kind + "-" + endpoint.id,
                            kind=kind,
                            mandatory=kind in required,
                            available=not reason,
                            source=capability.source,
                            reason=reason,
                        )
                    )
        elif kind in {"browser_e2e", "accessibility", "web_diagnostics"} and capability:
            for journey in project.journeys:
                items.append(
                    PlanItem(
                        id=kind + "-" + journey.id,
                        kind=kind,
                        mandatory=kind in required,
                        available=not reason,
                        source=capability.source,
                        reason=reason,
                    )
                )
        else:
            items.append(
                PlanItem(
                    id=kind,
                    kind=kind,
                    mandatory=kind in required,
                    available=not reason,
                    command_id=capability.command_id if capability else None,
                    source=capability.source if capability else "policy",
                    reason=reason,
                )
            )
    high_risk = bool(
        repository
        and any(
            any(token in path.lower() for token in ["auth", "login", "password", "lock", "requirements", "config"])
            for path in repository.changed_files
        )
    )
    risk = "HIGH" if high_risk else "LOW" if repository and request.base_ref else "UNKNOWN"
    return TestPlan(
        project_id=project.id,
        policy_version=project.policy.version,
        policy_hash=digest(project),
        request=request,
        repository=repository,
        items=items,
        required=sorted(required),
        risk_level=risk,
        impact_basis=[
            "owner_policy_floor",
            "conservative_conditional_rules" if not repository or not request.base_ref else "base_head_and_workspace_changed_paths",
        ],
    )


def definition(project, item):
    if item.kind in {"api", "smoke"}:
        return digest(next(e for e in project.api_endpoints if item.id == item.kind + "-" + e.id))
    if item.kind in {"browser_e2e", "accessibility", "web_diagnostics"}:
        return digest(next(j for j in project.journeys if item.id == item.kind + "-" + j.id))
    return digest([item.id, item.command_id, item.source])
