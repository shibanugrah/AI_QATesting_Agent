from __future__ import annotations

import pytest

from human_review.email_sender import ApprovedReportSender
from human_review.review_queue import ReviewQueue
from qa_agent.models import Report, RunRequest, TargetMode, TargetSite, TestCase, TestSuite
from qa_agent.planner import create_plan


def test_outbox_delivery_requires_approved_report(tmp_path) -> None:
    target = TargetSite(
        name="Demo",
        base_url="https://example.com",
        authorized=True,
        test_cases=[TestCase("smoke-home", "Home", TestSuite.SMOKE, "ui", "/")],
    )
    plan = create_plan(target, RunRequest(TargetMode.URL, [TestSuite.SMOKE]), target.test_cases)
    report = Report.create(target.name, plan, [])
    queue = ReviewQueue(tmp_path / "review")
    queue.submit(report)
    sender = ApprovedReportSender(queue, tmp_path / "outbox")

    with pytest.raises(PermissionError, match="blocked"):
        sender.send_report(report.id, "qa@example.com")

    queue.approve(report.id, "Reviewed")
    outbox_file = sender.send_report(report.id, "qa@example.com")

    assert outbox_file.exists()
    assert "qa@example.com" in outbox_file.read_text(encoding="utf-8")
