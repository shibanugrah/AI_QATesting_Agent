from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from uuid import uuid4

from agents.failure_analyzer import FailureAnalyzer
from agents.test_generator import TestGenerator
from human_review.review_queue import ReviewQueue
from qa_agent.models import Report, TargetSite, TestCase, TestResult
from reports.report_builder import ReportBuilder


class PhaseATests(unittest.TestCase):
    def test_generator_creates_api_and_ui_tests(self) -> None:
        target = TargetSite(
            name="Local",
            base_url="http://127.0.0.1",
            api_endpoints=["/health"],
            ui_paths=["/"],
        )

        tests = TestGenerator().generate(target)

        self.assertEqual([test.kind for test in tests], ["api", "ui"])

    def test_failure_analyzer_classifies_404(self) -> None:
        result = TestResult(
            test_case=TestCase(id="api-1", name="missing", kind="api", target="/missing"),
            status="failed",
            duration_ms=10,
            logs=["HTTP error: 404"],
            response_status=404,
            error="Not Found",
        )

        analysis = FailureAnalyzer().analyze([result])

        self.assertIn("missing", analysis[0].likely_cause.lower())

    def test_email_requires_human_approval(self) -> None:
        temp_dir = Path("artifacts") / "test_runs" / str(uuid4())
        queue = ReviewQueue(str(temp_dir / "queue"))
        report = Report.create("Local", [], [])
        report = ReportBuilder(str(temp_dir / "reports")).build(report)
        queue.submit(report)
        sender = _load_email_sender_class()(queue, str(temp_dir / "outbox"))

        with self.assertRaises(PermissionError):
            sender.send_report(report.id, "qa@example.com")

        queue.approve(report.id, "approved")
        path = sender.send_report(report.id, "qa@example.com")

        self.assertTrue(path.exists())
        self.assertIn("qa@example.com", path.read_text(encoding="utf-8"))


def _load_email_sender_class():
    root = Path(__file__).resolve().parent.parent
    sender_path = root / "email" / "email_sender.py"
    spec = importlib.util.spec_from_file_location("qa_agent_manual_email_sender_test", sender_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.EmailSender


if __name__ == "__main__":
    unittest.main()
