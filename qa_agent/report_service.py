from __future__ import annotations

from pathlib import Path

from human_review.review_queue import ReviewQueue
from qa_agent.email_loader import load_email_sender_class
from qa_agent.json_utils import read_json
from qa_agent.logging_utils import get_logger

logger = get_logger(__name__)


def list_review_records(queue_dir: str = "artifacts/review_queue") -> list[dict]:
    directory = Path(queue_dir)
    if not directory.exists():
        return []

    records = []
    for path in directory.glob("*.json"):
        try:
            record = read_json(path)
            record["_path"] = str(path)
            records.append(record)
        except Exception:
            logger.exception("Could not read review record %s", path)
    return sorted(records, key=lambda item: item["report"]["created_at"], reverse=True)


def result_counts(record: dict) -> dict[str, int]:
    results = record["report"].get("results", [])
    passed = len([result for result in results if result["status"] == "passed"])
    failed = len([result for result in results if result["status"] == "failed"])
    errors = len([result for result in results if result["status"] == "error"])
    skipped = len([result for result in results if result["status"] == "skipped"])
    return {
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "skipped": skipped,
    }


def summary_text(record: dict) -> str:
    report = record["report"]
    counts = result_counts(record)
    needs_attention = counts["failed"] + counts["errors"]
    return (
        f"{report['site_name']}: {counts['passed']}/{counts['total']} passed, "
        f"{needs_attention} need attention."
    )


def ai_insights(record: dict) -> list[str]:
    analyses = record["report"].get("analyses", [])
    if not analyses:
        return ["No failures found."]
    return [
        (
            f"{analysis['test_id']}: {analysis['likely_cause']} "
            f"Recommended: {analysis['recommendation']}"
        )
        for analysis in analyses
    ]


def approve_report(report_id: str, notes: str, queue: ReviewQueue | None = None) -> dict:
    return (queue or ReviewQueue()).approve(report_id, notes)


def reject_report(report_id: str, notes: str, queue: ReviewQueue | None = None) -> dict:
    return (queue or ReviewQueue()).reject(report_id, notes)


def send_approved_report(report_id: str, recipient: str, queue: ReviewQueue | None = None) -> Path:
    email_sender_class = load_email_sender_class()
    return email_sender_class(queue or ReviewQueue()).send_report(report_id, recipient)
