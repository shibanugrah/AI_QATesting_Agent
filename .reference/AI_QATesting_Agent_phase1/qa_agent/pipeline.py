from __future__ import annotations

from executor.api_runner import ApiRunner
from executor.ui_runner import UiRunner
from human_review.review_queue import ReviewQueue
from qa_agent.generator import TestGenerator
from qa_agent.models import Report, RunOutcome, RunRequest, TargetSite, TestCase, TestResult
from qa_agent.planner import create_plan
from qa_agent.security import validate_authorized_external_target
from reports.report_builder import ReportBuilder


class QAPipeline:
    def __init__(
        self,
        generator: TestGenerator | None = None,
        api_runner: ApiRunner | None = None,
        ui_runner: UiRunner | None = None,
        report_builder: ReportBuilder | None = None,
        review_queue: ReviewQueue | None = None,
    ) -> None:
        self.generator = generator or TestGenerator()
        self.api_runner = api_runner or ApiRunner()
        self.ui_runner = ui_runner or UiRunner()
        self.report_builder = report_builder or ReportBuilder()
        self.review_queue = review_queue or ReviewQueue()

    def plan(self, target: TargetSite, request: RunRequest):
        return create_plan(target, request, self.generator.generate(target))

    def run(self, target: TargetSite, request: RunRequest) -> RunOutcome:
        plan = self.plan(target, request)
        if request.dry_run:
            return RunOutcome(plan=plan, report=None)

        validate_authorized_external_target(target)
        results: list[TestResult] = []
        for index, test_case in enumerate(plan.included_tests):
            result = self._run_case(target, test_case)
            results.append(result)
            if request.fail_fast and result.status in {"failed", "error"}:
                results.extend(self._skipped_results(plan.included_tests[index + 1 :]))
                break

        report = Report.create(target.name, plan, results)
        report = self.report_builder.build(report)
        self.review_queue.submit(report)
        return RunOutcome(plan=plan, report=report)

    def _run_case(self, target: TargetSite, test_case: TestCase) -> TestResult:
        if test_case.kind == "api":
            return self.api_runner.run(target, test_case)
        return self.ui_runner.run(target, test_case)

    @staticmethod
    def _skipped_results(test_cases: list[TestCase]) -> list[TestResult]:
        return [
            TestResult(
                test_case=test_case,
                status="skipped",
                duration_ms=0,
                logs=["Skipped because fail-fast stopped the selected test plan."],
            )
            for test_case in test_cases
        ]
