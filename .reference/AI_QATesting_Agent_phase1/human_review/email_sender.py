from __future__ import annotations

from pathlib import Path

from human_review.review_queue import ReviewQueue


class ApprovedReportSender:
    """Creates a local outbox record only after human approval; it does not send real email."""

    def __init__(self, queue: ReviewQueue, outbox_root: str | Path = "artifacts/outbox") -> None:
        self.queue = queue
        self.outbox_root = Path(outbox_root)
        self.outbox_root.mkdir(parents=True, exist_ok=True)

    def send_report(self, report_id: str, recipient: str) -> Path:
        record = self.queue.get(report_id)
        if record["approval_status"] != "approved":
            raise PermissionError("Report delivery is blocked until a human approves the report.")
        report = record["report"]
        path = self.outbox_root / f"{report_id}.eml.txt"
        path.write_text(
            f"To: {recipient}\n"
            f"Subject: QA report for {report['site_name']}\n\n"
            f"Approved QA report: {report.get('html_path') or 'report path unavailable'}\n",
            encoding="utf-8",
        )
        return path
