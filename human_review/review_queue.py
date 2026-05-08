from __future__ import annotations

from pathlib import Path

from qa_agent.json_utils import read_json, write_json
from qa_agent.logging_utils import get_logger
from qa_agent.models import ApprovalStatus, Report, to_dict

logger = get_logger(__name__)


class ReviewQueue:
    def __init__(self, queue_dir: str = "artifacts/review_queue") -> None:
        self.queue_dir = Path(queue_dir)
        self.queue_dir.mkdir(parents=True, exist_ok=True)

    def submit(self, report: Report) -> Path:
        record = {
            "report": to_dict(report),
            "approval_status": "pending",
            "review_notes": "",
        }
        path = self._path(report.id)
        write_json(path, record)
        logger.info("Submitted report %s for human review", report.id)
        return path

    def approve(self, report_id: str, notes: str = "") -> dict:
        return self._set_status(report_id, "approved", notes)

    def reject(self, report_id: str, notes: str = "") -> dict:
        return self._set_status(report_id, "rejected", notes)

    def get(self, report_id: str) -> dict:
        return read_json(self._path(report_id))

    def is_approved(self, report_id: str) -> bool:
        return self.get(report_id)["approval_status"] == "approved"

    def _set_status(self, report_id: str, status: ApprovalStatus, notes: str) -> dict:
        record = self.get(report_id)
        record["approval_status"] = status
        record["review_notes"] = notes
        write_json(self._path(report_id), record)
        logger.info("Report %s status changed to %s", report_id, status)
        return record

    def _path(self, report_id: str) -> Path:
        return self.queue_dir / f"{report_id}.json"

