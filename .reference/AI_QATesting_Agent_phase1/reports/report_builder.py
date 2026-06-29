from __future__ import annotations

from html import escape
from pathlib import Path

from qa_agent.models import Report


class ReportBuilder:
    def __init__(self, root: str | Path = "artifacts/reports") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def build(self, report: Report) -> Report:
        path = self.root / f"{report.id}.html"
        path.write_text(self._render(report), encoding="utf-8")
        report.html_path = str(path)
        return report

    def _render(self, report: Report) -> str:
        selected = ", ".join(suite.value for suite in report.selected_suites)
        result_rows = "\n".join(
            "<tr>"
            f"<td>{escape(result.test_case.id)}</td>"
            f"<td>{escape(result.test_case.suite.value)}</td>"
            f"<td>{escape(result.test_case.name)}</td>"
            f"<td>{escape(result.status)}</td>"
            f"<td>{result.duration_ms}</td>"
            f"<td>{escape(result.error or '')}</td>"
            "</tr>"
            for result in report.results
        )
        excluded_rows = "\n".join(
            "<tr>"
            f"<td>{escape(item.test_case.id)}</td>"
            f"<td>{escape(item.test_case.suite.value)}</td>"
            f"<td>{escape(item.reason)}</td>"
            "</tr>"
            for item in report.plan.excluded_tests
        ) or "<tr><td colspan='3'>No tests excluded.</td></tr>"
        return f"""<!doctype html>
<html lang='en'>
<head><meta charset='utf-8'><title>QA report {escape(report.id)}</title>
<style>body{{font-family:Arial,sans-serif;margin:2rem}} table{{border-collapse:collapse;width:100%;margin:1rem 0}} td,th{{border:1px solid #bbb;padding:.5rem;text-align:left}} th{{background:#eee}}</style>
</head>
<body>
<h1>QA Report: {escape(report.site_name)}</h1>
<p><strong>Report ID:</strong> {escape(report.id)}<br>
<strong>Created:</strong> {escape(report.created_at)}<br>
<strong>Selected suites:</strong> {escape(selected)}<br>
<strong>Target mode:</strong> {escape(report.plan.target_mode.value)}<br>
<strong>Environment:</strong> {escape(report.plan.environment)}</p>
<h2>Executed tests</h2>
<table><thead><tr><th>ID</th><th>Suite</th><th>Name</th><th>Status</th><th>Duration (ms)</th><th>Error</th></tr></thead><tbody>{result_rows}</tbody></table>
<h2>Excluded tests</h2>
<table><thead><tr><th>ID</th><th>Suite</th><th>Reason</th></tr></thead><tbody>{excluded_rows}</tbody></table>
<p>Report delivery remains blocked until human approval.</p>
</body></html>"""
