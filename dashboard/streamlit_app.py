from __future__ import annotations

from urllib.parse import urlparse

import streamlit as st
import streamlit.components.v1 as components

from human_review.review_queue import ReviewQueue
from qa_agent.logging_utils import configure_logging
from qa_agent.models import TargetSite
from qa_agent.pipeline import QAPipeline
from qa_agent.report_service import (
    ai_insights,
    approve_report,
    list_review_records,
    reject_report,
    result_counts,
    send_approved_report,
    summary_text,
)


def main() -> None:
    configure_logging()
    configure_page()
    render_header()
    render_run_panel()
    render_reports_panel()


def configure_page() -> None:
    st.set_page_config(page_title="AI QA Agent", layout="wide")
    st.markdown(
        """
        <style>
        .block-container { padding-top: 2rem; max-width: 1180px; }
        div[data-testid="stMetric"] {
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            padding: 12px 14px;
            background: #ffffff;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header() -> None:
    st.title("AI QA Agent")
    st.caption("Run tests, review reports, approve delivery, and inspect AI failure insights.")


def render_run_panel() -> None:
    with st.container(border=True):
        st.subheader("Run Test")
        with st.form("run_test_form"):
            name = st.text_input("Project name", value="My Website")
            base_url = st.text_input("Base URL", placeholder="https://example.com")
            api_endpoints = st.text_area("API endpoints", value="/", help="One endpoint per line.")
            ui_paths = st.text_area("UI paths", value="/", help="One path per line.")
            submitted = st.form_submit_button("Run test", type="primary")

        if submitted:
            run_dashboard_test(name, base_url, api_endpoints, ui_paths)


def run_dashboard_test(name: str, base_url: str, api_text: str, ui_text: str) -> None:
    if not is_valid_url(base_url):
        st.error("Enter a valid URL, including http:// or https://.")
        return

    target = TargetSite(
        name=name.strip() or host_name(base_url),
        base_url=base_url.strip(),
        api_endpoints=parse_lines(api_text),
        ui_paths=parse_lines(ui_text) or ["/"],
    )
    with st.spinner("Running QA pipeline..."):
        report = QAPipeline(review_queue=ReviewQueue()).run(target)
    st.success(f"Report created: {report.id}")
    st.session_state["selected_report_id"] = report.id


def render_reports_panel() -> None:
    records = list_review_records()
    st.subheader("Latest Reports")

    if not records:
        st.info("No reports yet. Run a test to create the first review item.")
        return

    selected = select_report(records)
    if selected is None:
        return

    render_summary(selected)
    render_report_tabs(selected)


def select_report(records: list[dict]) -> dict | None:
    labels = [report_label(record) for record in records]
    selected_id = st.session_state.get("selected_report_id")
    index = next(
        (
            position
            for position, record in enumerate(records)
            if record["report"]["id"] == selected_id
        ),
        0,
    )
    label = st.selectbox("Report", labels, index=index)
    return records[labels.index(label)] if label else None


def render_summary(record: dict) -> None:
    counts = result_counts(record)
    status = record["approval_status"]
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Passed", counts["passed"])
    col2.metric("Failed", counts["failed"])
    col3.metric("Errors", counts["errors"])
    col4.metric("Total", counts["total"])
    col5.metric("Review", status.title())
    st.write(summary_text(record))


def render_report_tabs(record: dict) -> None:
    overview_tab, insights_tab, review_tab, html_tab = st.tabs(
        ["Summary", "AI Insights", "Review", "HTML Report"]
    )
    with overview_tab:
        render_results(record)
    with insights_tab:
        render_insights(record)
    with review_tab:
        render_review_actions(record)
    with html_tab:
        render_html_report(record)


def render_results(record: dict) -> None:
    results = record["report"].get("results", [])
    if not results:
        st.info("This report has no test results.")
        return

    rows = [
        {
            "Test": result["test_case"]["name"],
            "Kind": result["test_case"]["kind"],
            "Status": result["status"],
            "Duration ms": result["duration_ms"],
            "Error": result.get("error") or "",
        }
        for result in results
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)


def render_insights(record: dict) -> None:
    for insight in ai_insights(record):
        st.info(insight)


def render_review_actions(record: dict) -> None:
    report_id = record["report"]["id"]
    notes = st.text_input("Review notes", key=f"notes_{report_id}")
    approve_col, reject_col = st.columns(2)

    if approve_col.button("Approve", key=f"approve_{report_id}", type="primary"):
        approve_report(report_id, notes)
        st.success("Report approved.")
        st.rerun()

    if reject_col.button("Reject", key=f"reject_{report_id}"):
        reject_report(report_id, notes)
        st.warning("Report rejected.")
        st.rerun()

    st.divider()
    recipient = st.text_input("Email recipient", key=f"email_{report_id}")
    if st.button("Send approved report", key=f"send_{report_id}"):
        send_report_from_dashboard(report_id, recipient)


def send_report_from_dashboard(report_id: str, recipient: str) -> None:
    if not recipient.strip():
        st.error("Enter an email recipient.")
        return
    try:
        path = send_approved_report(report_id, recipient.strip())
        st.success(f"Email prepared: {path}")
    except PermissionError as exc:
        st.error(str(exc))


def render_html_report(record: dict) -> None:
    html_path = record["report"].get("html_path")
    if not html_path:
        st.info("No HTML report path is stored for this report.")
        return

    st.code(html_path)
    try:
        with open(html_path, "r", encoding="utf-8") as report_file:
            components.html(report_file.read(), height=560, scrolling=True)
    except FileNotFoundError:
        st.error("The HTML report file is missing.")


def parse_lines(value: str) -> list[str]:
    return [line.strip() for line in value.splitlines() if line.strip()]


def is_valid_url(value: str) -> bool:
    parsed = urlparse(value.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def host_name(value: str) -> str:
    return urlparse(value).netloc or "Website"


def report_label(record: dict) -> str:
    report = record["report"]
    return f"{report['created_at']} | {report['site_name']} | {record['approval_status']} | {report['id']}"


if __name__ == "__main__":
    main()
