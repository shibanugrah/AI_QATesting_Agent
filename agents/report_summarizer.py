from __future__ import annotations

from qa_agent.logging_utils import get_logger
from qa_agent.models import Report

logger = get_logger(__name__)


class ReportSummarizer:
    def summarize(self, report: Report) -> str:
        total = len(report.results)
        passed = len([result for result in report.results if result.status == "passed"])
        failed = len([result for result in report.results if result.status in {"failed", "error"}])
        summary = f"{report.site_name}: {passed}/{total} passed, {failed} need attention."
        logger.info("Report summary: %s", summary)
        return summary

