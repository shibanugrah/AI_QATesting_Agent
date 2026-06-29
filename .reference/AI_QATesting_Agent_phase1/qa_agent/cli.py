from __future__ import annotations

import argparse
from collections.abc import Sequence

from human_review.email_sender import ApprovedReportSender
from human_review.review_queue import ReviewQueue
from qa_agent.config import ConfigError, load_target
from qa_agent.models import RunRequest, TargetMode, TestSuite
from qa_agent.pipeline import QAPipeline
from qa_agent.planner import PlanError
from qa_agent.security import TargetSafetyError


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    queue = ReviewQueue()

    try:
        if args.command in {"plan", "run"}:
            target = load_target(args.config)
            request = _request_from_args(args, target.environment)
            pipeline = QAPipeline(review_queue=queue)
            if args.command == "plan":
                _print_plan(pipeline.plan(target, request))
                return 0

            outcome = pipeline.run(target, request)
            _print_plan(outcome.plan)
            if outcome.report is None:
                print("Dry run: no tests executed and no report created.")
                return 0
            print(f"Report ID: {outcome.report.id}")
            print(f"HTML report: {outcome.report.html_path}")
            print("Approval status: pending")
            return 0

        if args.command == "approve":
            queue.approve(args.report_id, args.notes)
            print(f"Approved report {args.report_id}")
            return 0

        if args.command == "reject":
            queue.reject(args.report_id, args.notes)
            print(f"Rejected report {args.report_id}")
            return 0

        if args.command == "send-email":
            path = ApprovedReportSender(queue).send_report(args.report_id, args.to)
            print(f"Prepared approved email: {path}")
            return 0
    except (ConfigError, PlanError, TargetSafetyError, PermissionError, FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))
    return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Selective AI QA Testing Agent (Phase 1)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name, help_text in (("plan", "Preview selected tests without execution"), ("run", "Run selected tests")):
        command = subparsers.add_parser(name, help=help_text)
        command.add_argument("--config", required=True, help="Path to validated target config JSON")
        command.add_argument(
            "--suite",
            action="append",
            required=True,
            choices=[suite.value for suite in TestSuite],
            help="Suite to include. Repeat --suite to select multiple suites.",
        )
        command.add_argument("--target-mode", choices=[mode.value for mode in TargetMode], default="url")
        command.add_argument("--environment", choices=["local", "demo", "staging"])
        command.add_argument("--fail-fast", action="store_true")
        if name == "run":
            command.add_argument("--dry-run", action="store_true")

    approve = subparsers.add_parser("approve", help="Approve a report for local delivery preparation")
    approve.add_argument("report_id")
    approve.add_argument("--notes", default="")

    reject = subparsers.add_parser("reject", help="Reject a report")
    reject.add_argument("report_id")
    reject.add_argument("--notes", default="")

    send = subparsers.add_parser("send-email", help="Prepare an outbox file for an approved report")
    send.add_argument("report_id")
    send.add_argument("--to", required=True)
    return parser


def _request_from_args(args: argparse.Namespace, config_environment: str) -> RunRequest:
    return RunRequest(
        target_mode=TargetMode(args.target_mode),
        selected_suites=[TestSuite(suite) for suite in args.suite],
        environment=args.environment or config_environment,
        fail_fast=args.fail_fast,
        dry_run=getattr(args, "dry_run", False),
    )


def _print_plan(plan) -> None:
    selected = ", ".join(suite.value for suite in plan.selected_suites)
    print(f"Selected suites: {selected}")
    print(f"Target mode: {plan.target_mode.value}")
    print(f"Environment: {plan.environment}")
    print(f"Included tests: {len(plan.included_tests)}")
    for test_case in plan.included_tests:
        print(f"  + {test_case.id} [{test_case.suite.value}] {test_case.name}")
    print(f"Excluded tests: {len(plan.excluded_tests)}")
    for excluded in plan.excluded_tests:
        print(f"  - {excluded.test_case.id}: {excluded.reason}")


if __name__ == "__main__":
    raise SystemExit(main())
