from __future__ import annotations

from agents.failure_analyzer import FailureAnalyzer
from agents.report_summarizer import ReportSummarizer
from agents.test_generator import TestGenerator
from executor.api_runner import ApiRunner
from executor.selenium_runner import SeleniumRunner
from human_review.review_queue import ReviewQueue
from rag.retriever import Retriever
from reports.report_builder import ReportBuilder

from qa_agent.logging_utils import get_logger
from qa_agent.models import Report, TargetSite, TestResult

logger = get_logger(__name__)


class QAPipeline:
    def __init__(
        self,
        generator: TestGenerator | None = None,
        api_runner: ApiRunner | None = None,
        ui_runner: SeleniumRunner | None = None,
        retriever: Retriever | None = None,
        report_builder: ReportBuilder | None = None,
        review_queue: ReviewQueue | None = None,
    ) -> None:
        self.generator = generator or TestGenerator()
        self.api_runner = api_runner or ApiRunner()
        self.ui_runner = ui_runner or SeleniumRunner()
        self.retriever = retriever or Retriever()
        self.analyzer = FailureAnalyzer(self.retriever)
        self.report_builder = report_builder or ReportBuilder()
        self.review_queue = review_queue or ReviewQueue()
        self.summarizer = ReportSummarizer()

    def run(self, target: TargetSite) -> Report:
        logger.info("Starting QA pipeline for %s", target.name)
        test_cases = self.generator.generate(target)
        results = [self._run_case(target, test_case) for test_case in test_cases]
        for result in results:
            if result.status in {"failed", "error"}:
                self.retriever.remember_failure(result)
        analyses = self.analyzer.analyze(results)
        report = Report.create(target.name, results, analyses)
        report = self.report_builder.build(report)
        self.review_queue.submit(report)
        logger.info(self.summarizer.summarize(report))
        return report

    def _run_case(self, target: TargetSite, test_case) -> TestResult:
        if test_case.kind == "api":
            return self.api_runner.run(target, test_case)
        return self.ui_runner.run(target, test_case)

