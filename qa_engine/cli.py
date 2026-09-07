from __future__ import annotations

import argparse
import json
from pathlib import Path

from pydantic import ValidationError

from qa_engine.domain import GitHubPR, Project, RunRequest
from qa_engine.engine import Engine
from qa_engine.repository import discover
from qa_engine.security import PolicyBlocked


def emit(value):
    if isinstance(value, list):
        value = [v.model_dump(mode="json") if hasattr(v, "model_dump") else v for v in value]
    elif hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    print(json.dumps(value, indent=2))


def main(argv=None):
    parser = argparse.ArgumentParser(description="QA Engine: independent verification for enrolled projects")
    parser.add_argument("--data-dir", default=".qa-engine")
    commands = parser.add_subparsers(dest="command", required=True)
    enroll = commands.add_parser("enroll", help="Owner authorization: store reviewed project policy")
    enroll.add_argument("config")
    for name in ["discover", "plan", "run", "verify-change", "investigate", "verify-fix"]:
        p = commands.add_parser(name)
        p.add_argument("project_id")
        if name != "discover":
            p.add_argument("--profile", action="append", default=[])
            p.add_argument("--base")
            p.add_argument("--head", default="HEAD")
            p.add_argument("--dry-run", action="store_true")
            p.add_argument("--context", default="")
            p.add_argument("--github-event", help="Optional GitHub event JSON; SHA must match actual checkout and --base")
            if name == "verify-fix":
                p.add_argument("--previous-run", required=True)
    for name in ["show", "gate", "review-report", "export"]:
        p = commands.add_parser(name)
        p.add_argument("project_id")
        p.add_argument("run_id")
        if name == "review-report":
            p.add_argument("decision", choices=["APPROVED", "REJECTED"])
            p.add_argument("--reviewer", required=True)
        if name == "export":
            p.add_argument("destination")
    search = commands.add_parser("memory-search")
    search.add_argument("project_id")
    search.add_argument("query")
    review = commands.add_parser("memory-review")
    review.add_argument("project_id")
    review.add_argument("record_id")
    review.add_argument("decision", choices=["APPROVED", "REJECTED", "STALE", "EXPIRED"])
    review.add_argument("--reviewer", required=True)
    args = parser.parse_args(argv)
    try:
        engine = Engine(args.data_dir)
        if args.command == "enroll":
            path = Path(args.config).resolve()
            project = Project.model_validate_json(path.read_text(encoding="utf-8"))
            if project.repository and not Path(project.repository).is_absolute():
                project.repository = str((path.parent / project.repository).resolve())
            enrolled = engine.enroll(project)
            emit({"project_id": enrolled.id, "environment": enrolled.environment, "enrolled": True})
        elif args.command == "discover":
            emit(discover(engine.store.project(args.project_id)))
        elif args.command in {"show", "gate", "review-report", "export"}:
            if args.command == "show":
                emit(engine.get_run(args.project_id, args.run_id))
            elif args.command == "gate":
                result = engine.gate(args.project_id, args.run_id)
                emit(result)
                return {"PASS": 0, "FAIL": 1, "REVIEW_REQUIRED": 2, "NOT_EVALUATED": 3}[result.decision]
            elif args.command == "review-report":
                emit(engine.review_report(args.project_id, args.run_id, args.decision, reviewer=args.reviewer))
            else:
                emit({"path": engine.export_report(args.project_id, args.run_id, args.destination)})
        elif args.command == "memory-search":
            emit(engine.find_incidents(args.project_id, args.query))
        elif args.command == "memory-review":
            emit(engine.review_memory(args.project_id, args.record_id, args.decision, reviewer=args.reviewer))
        else:
            operation = {"verify-change": "VERIFY_CHANGE", "investigate": "INVESTIGATE_BUG", "verify-fix": "VERIFY_FIX"}.get(
                args.command, "TEST_TARGET"
            )
            request = RunRequest(
                project_id=args.project_id,
                operation=operation,
                profiles=args.profile,
                base_ref=args.base,
                head_ref=args.head,
                dry_run=args.dry_run,
                context=args.context,
                previous_run_id=getattr(args, "previous_run", None),
            )
            if args.github_event:
                event = json.loads(Path(args.github_event).read_text(encoding="utf-8"))
                pr = event["pull_request"]
                request.github_pr = GitHubPR(
                    repository=event["repository"]["full_name"], number=pr["number"], base_sha=pr["base"]["sha"], head_sha=pr["head"]["sha"]
                )
            if args.command == "plan":
                emit(engine.plan(request))
            else:
                result = engine.run(request)
                emit(result)
                return (
                    0
                    if args.dry_run and result.run_status == "COMPLETED"
                    else {"PASS": 0, "FAIL": 1, "REVIEW_REQUIRED": 2, "NOT_EVALUATED": 3}[result.gate.decision]
                )
    except (ValidationError, PolicyBlocked, KeyError, OSError, ValueError) as exc:
        emit({"error": "CONFIG_VALIDATION_ERROR" if isinstance(exc, ValidationError) else type(exc).__name__})
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
