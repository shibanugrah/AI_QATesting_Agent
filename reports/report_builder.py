from __future__ import annotations

from html import escape
from pathlib import Path

from qa_agent.logging_utils import get_logger
from qa_agent.models import FailureAnalysis, Report, TestResult

logger = get_logger(__name__)


class ReportBuilder:
    def __init__(self, output_dir: str = "artifacts/reports") -> None:
        self.output_dir = Path(output_dir)

    def build(self, report: Report) -> Report:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.output_dir / f"{report.id}.html"
        path.write_text(self._html(report), encoding="utf-8")
        report.html_path = str(path)
        logger.info("Built HTML report at %s", path)
        return report

    def _html(self, report: Report) -> str:
        rows = "\n".join(self._result_row(result) for result in report.results)
        analyses = "\n".join(self._analysis_block(analysis) for analysis in report.analyses)
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>QA Report - {escape(report.site_name)}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 32px; color: #1f2937; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 16px; }}
    th, td {{ border: 1px solid #d1d5db; padding: 8px; text-align: left; }}
    th {{ background: #f3f4f6; }}
    .passed {{ color: #047857; font-weight: 700; }}
    .failed, .error {{ color: #b91c1c; font-weight: 700; }}
    .analysis {{ border-left: 4px solid #2563eb; padding: 8px 12px; margin: 12px 0; background: #eff6ff; }}
  </style>
</head>
<body>
  <h1>QA Report: {escape(report.site_name)}</h1>
  <p>Created: {escape(report.created_at)}</p>
  <h2>Results</h2>
  <table>
    <thead><tr><th>Test</th><th>Kind</th><th>Status</th><th>Duration</th><th>Error</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
  <h2>Failure Analysis</h2>
  {analyses or "<p>No failures found.</p>"}
</body>
</html>
"""

    @staticmethod
    def _result_row(result: TestResult) -> str:
        return (
            "<tr>"
            f"<td>{escape(result.test_case.name)}</td>"
            f"<td>{escape(result.test_case.kind)}</td>"
            f"<td class=\"{escape(result.status)}\">{escape(result.status)}</td>"
            f"<td>{result.duration_ms} ms</td>"
            f"<td>{escape(result.error or '')}</td>"
            "</tr>"
        )

    @staticmethod
    def _analysis_block(analysis: FailureAnalysis) -> str:
        similar = "".join(f"<li>{escape(item[:240])}</li>" for item in analysis.similar_failures)
        return f"""<section class="analysis">
  <h3>{escape(analysis.test_id)}</h3>
  <p><strong>Summary:</strong> {escape(analysis.summary)}</p>
  <p><strong>Likely cause:</strong> {escape(analysis.likely_cause)}</p>
  <p><strong>Recommendation:</strong> {escape(analysis.recommendation)}</p>
  {"<ul>" + similar + "</ul>" if similar else ""}
</section>"""

