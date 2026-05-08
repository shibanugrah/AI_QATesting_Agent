from __future__ import annotations

from rag.retriever import Retriever

from qa_agent.logging_utils import get_logger
from qa_agent.models import FailureAnalysis, TestResult

logger = get_logger(__name__)


class FailureAnalyzer:
    def __init__(self, retriever: Retriever | None = None) -> None:
        self.retriever = retriever

    def analyze(self, results: list[TestResult]) -> list[FailureAnalysis]:
        failures = [result for result in results if result.status in {"failed", "error"}]
        logger.info("Analyzing %d failures", len(failures))
        return [self._analyze_one(result) for result in failures]

    def _analyze_one(self, result: TestResult) -> FailureAnalysis:
        log_text = "\n".join(result.logs + ([result.error] if result.error else []))
        similar = self.retriever.retrieve(log_text, limit=3) if self.retriever else []
        likely_cause = self._likely_cause(result)
        recommendation = self._recommendation(result)
        return FailureAnalysis(
            test_id=result.test_case.id,
            summary=f"{result.test_case.name} ended with {result.status}.",
            likely_cause=likely_cause,
            recommendation=recommendation,
            similar_failures=[item["text"] for item in similar],
        )

    @staticmethod
    def _likely_cause(result: TestResult) -> str:
        if result.response_status and result.response_status >= 500:
            return "Server-side failure or dependency outage."
        if result.response_status == 404:
            return "Endpoint or route may be missing or misconfigured."
        if result.response_status and result.response_status >= 400:
            return "Client request, auth, or validation problem."
        if result.status == "error":
            return "Network, DNS, timeout, or browser setup issue."
        return "Response content or status did not match expectations."

    @staticmethod
    def _recommendation(result: TestResult) -> str:
        if result.test_case.kind == "api":
            return "Check API route, environment URL, auth headers, and recent backend changes."
        return "Check page route, critical JS errors, rendering blockers, and locator stability."

