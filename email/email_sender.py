from __future__ import annotations

from pathlib import Path

from human_review.review_queue import ReviewQueue
from qa_agent.logging_utils import get_logger

logger = get_logger(__name__)


class EmailSender:
    """Manual trigger sender guarded by human approval.

    The MVP writes an outbox file. Replace _deliver with SMTP/provider code when
    you are ready, keeping the approval check in send_report.
    """

    def __init__(self, review_queue: ReviewQueue, outbox_dir: str = "artifacts/outbox") -> None:
        self.review_queue = review_queue
        self.outbox_dir = Path(outbox_dir)

    def send_report(self, report_id: str, recipient: str) -> Path:
        if not self.review_queue.is_approved(report_id):
            logger.warning("Blocked email for unapproved report %s", report_id)
            raise PermissionError("Human approval is required before email can be sent.")

        record = self.review_queue.get(report_id)
        report = record["report"]
        self.outbox_dir.mkdir(parents=True, exist_ok=True)
        message_path = self.outbox_dir / f"{report_id}.eml.txt"
        message_path.write_text(
            "\n".join(
                [
                    f"To: {recipient}",
                    f"Subject: QA Report - {report['site_name']}",
                    "",
                    f"Report approved for delivery: {report.get('html_path')}",
                    f"Review notes: {record.get('review_notes', '')}",
                ]
            ),
            encoding="utf-8",
        )
        logger.info("Prepared approved email for %s at %s", report_id, message_path)
        return message_path
