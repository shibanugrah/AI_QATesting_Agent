from __future__ import annotations

import argparse
import json
from pathlib import Path

from human_review.approval_api import run_server
from human_review.review_queue import ReviewQueue
from qa_agent.email_loader import load_email_sender_class
from qa_agent.logging_utils import configure_logging
from qa_agent.models import TargetSite
from qa_agent.pipeline import QAPipeline
from scheduler.job_queue import JobQueue
from scheduler.worker import Worker


def main() -> None:
    configure_logging()
    parser = argparse.ArgumentParser(description="AI QA Testing Agent")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run Phase A/B pipeline for one target")
    run_parser.add_argument("--config", required=True, help="Path to target config JSON")

    approve_parser = subparsers.add_parser("approve", help="Approve a queued report")
    approve_parser.add_argument("report_id")
    approve_parser.add_argument("--notes", default="")

    reject_parser = subparsers.add_parser("reject", help="Reject a queued report")
    reject_parser.add_argument("report_id")
    reject_parser.add_argument("--notes", default="")

    send_parser = subparsers.add_parser("send-email", help="Prepare approved email")
    send_parser.add_argument("report_id")
    send_parser.add_argument("--to", required=True)

    api_parser = subparsers.add_parser("approval-api", help="Start local approval API")
    api_parser.add_argument("--host", default="127.0.0.1")
    api_parser.add_argument("--port", type=int, default=8088)

    batch_parser = subparsers.add_parser("batch", help="Run multiple target configs")
    batch_parser.add_argument("--configs", nargs="+", required=True)
    batch_parser.add_argument("--parallelism", type=int, default=2)

    args = parser.parse_args()
    queue = ReviewQueue()

    if args.command == "run":
        report = QAPipeline(review_queue=queue).run(_load_target(args.config))
        print(f"Report ID: {report.id}")
        print(f"HTML report: {report.html_path}")
        print("Approval status: pending")
    elif args.command == "approve":
        queue.approve(args.report_id, args.notes)
        print(f"Approved report {args.report_id}")
    elif args.command == "reject":
        queue.reject(args.report_id, args.notes)
        print(f"Rejected report {args.report_id}")
    elif args.command == "send-email":
        email_sender_class = load_email_sender_class()
        path = email_sender_class(queue).send_report(args.report_id, args.to)
        print(f"Prepared approved email: {path}")
    elif args.command == "approval-api":
        run_server(args.host, args.port)
    elif args.command == "batch":
        job_queue = JobQueue()
        for config in args.configs:
            job_queue.enqueue(_load_target(config))
        reports = Worker().run_batch(job_queue, args.parallelism)
        for report in reports:
            print(f"{report.site_name}: {report.id} -> {report.html_path}")


def _load_target(path: str) -> TargetSite:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return TargetSite(
        name=data["name"],
        base_url=data["base_url"],
        api_endpoints=data.get("api_endpoints", []),
        ui_paths=data.get("ui_paths", ["/"]),
    )


if __name__ == "__main__":
    main()
