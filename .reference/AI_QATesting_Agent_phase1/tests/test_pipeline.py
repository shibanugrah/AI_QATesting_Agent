from __future__ import annotations

from human_review.review_queue import ReviewQueue
from qa_agent.models import RunRequest, TargetMode, TargetSite, TestCase, TestResult, TestSuite
from qa_agent.pipeline import QAPipeline
from reports.report_builder import ReportBuilder


class RecordingRunner:
    def __init__(self) -> None:
        self.executed: list[str] = []

    def run(self, _target: TargetSite, test_case: TestCase) -> TestResult:
        self.executed.append(test_case.id)
        return TestResult(test_case=test_case, status="passed", duration_ms=1, logs=["recorded"])


def _target() -> TargetSite:
    return TargetSite(
        name="Demo",
        base_url="https://example.com",
        authorized=True,
        test_cases=[
            TestCase("smoke-home", "Home loads", TestSuite.SMOKE, "ui", "/"),
            TestCase("api-health", "Health endpoint", TestSuite.API, "api", "/api/health"),
        ],
    )


def test_pipeline_executes_only_selected_suite_and_queues_report(tmp_path) -> None:
    api_runner = RecordingRunner()
    ui_runner = RecordingRunner()
    pipeline = QAPipeline(
        api_runner=api_runner,
        ui_runner=ui_runner,
        report_builder=ReportBuilder(tmp_path / "reports"),
        review_queue=ReviewQueue(tmp_path / "review_queue"),
    )

    outcome = pipeline.run(_target(), RunRequest(TargetMode.URL, [TestSuite.SMOKE]))

    assert ui_runner.executed == ["smoke-home"]
    assert api_runner.executed == []
    assert outcome.report is not None
    assert [result.test_case.id for result in outcome.report.results] == ["smoke-home"]
    assert outcome.report.html_path is not None
    record = ReviewQueue(tmp_path / "review_queue").get(outcome.report.id)
    assert record["approval_status"] == "pending"
    assert record["report"]["selected_suites"] == ["smoke"]


def test_dry_run_does_not_execute_or_create_report(tmp_path) -> None:
    api_runner = RecordingRunner()
    ui_runner = RecordingRunner()
    pipeline = QAPipeline(
        api_runner=api_runner,
        ui_runner=ui_runner,
        report_builder=ReportBuilder(tmp_path / "reports"),
        review_queue=ReviewQueue(tmp_path / "review_queue"),
    )

    outcome = pipeline.run(
        _target(),
        RunRequest(TargetMode.URL, [TestSuite.SMOKE], dry_run=True),
    )

    assert outcome.report is None
    assert ui_runner.executed == []
    assert api_runner.executed == []
    assert not list((tmp_path / "review_queue").glob("*.json"))
