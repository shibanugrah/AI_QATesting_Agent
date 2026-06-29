from __future__ import annotations

"""Run with: streamlit run dashboard/streamlit_app.py

The dashboard is optional. Core planning and execution work through the CLI without Streamlit.
"""

from pathlib import Path

import streamlit as st

from human_review.review_queue import ReviewQueue
from qa_agent.models import RunRequest, TargetMode, TargetSite, TestSuite
from qa_agent.pipeline import QAPipeline
from qa_agent.planner import PlanError
from qa_agent.security import TargetSafetyError

SUPPORTED = [TestSuite.SMOKE, TestSuite.API]
PLANNED = [
    TestSuite.UNIT,
    TestSuite.INTEGRATION,
    TestSuite.E2E,
    TestSuite.REGRESSION,
    TestSuite.ACCESSIBILITY,
    TestSuite.VISUAL,
    TestSuite.SECURITY_BASELINE,
]


def main() -> None:
    st.set_page_config(page_title="Selective QA Agent", layout="wide")
    st.title("Selective QA Agent")
    st.caption("Plan and run only Smoke or API checks. Human approval remains required before report delivery.")

    with st.container(border=True):
        st.subheader("1. Choose target and suites")
        with st.form("target_form"):
            name = st.text_input("Project name", value="My Website")
            base_url = st.text_input("Base URL", placeholder="https://staging.example.com")
            authorized = st.checkbox("I own or am explicitly authorized to test this target")
            environment = st.selectbox("Environment", ["local", "demo", "staging"], index=1)
            suites = st.multiselect(
                "Executable suites",
                options=SUPPORTED,
                default=[TestSuite.SMOKE],
                format_func=lambda suite: suite.value.title(),
            )
            st.caption("Planned but disabled: " + ", ".join(suite.value for suite in PLANNED))
            api_endpoints = st.text_area("API endpoints", value="/api/health", help="One safe GET endpoint per line.")
            ui_paths = st.text_area("UI paths", value="/", help="One path per line.")
            preview = st.form_submit_button("Preview Test Plan")

        if preview:
            target = _target(name, base_url, api_endpoints, ui_paths, authorized, environment)
            request = RunRequest(TargetMode.URL, list(suites), environment=environment)
            try:
                plan = QAPipeline().plan(target, request)
            except (PlanError, ValueError) as exc:
                st.error(str(exc))
                return
            st.session_state["target"] = target
            st.session_state["request"] = request
            st.session_state["plan"] = plan

    plan = st.session_state.get("plan")
    if plan:
        st.subheader("2. Preview test plan")
        left, right = st.columns(2)
        with left:
            st.success("Included")
            for test_case in plan.included_tests:
                st.write(f"✓ `{test_case.id}` — {test_case.name}")
        with right:
            st.info("Excluded")
            for item in plan.excluded_tests:
                st.write(f"– `{item.test_case.id}` — {item.reason}")

        if st.button("Run Selected Tests", type="primary"):
            request = st.session_state["request"]
            target = st.session_state["target"]
            try:
                outcome = QAPipeline(review_queue=ReviewQueue()).run(target, request)
            except TargetSafetyError as exc:
                st.error(str(exc))
                return
            st.session_state["report_id"] = outcome.report.id if outcome.report else None
            st.success(f"Report created: {outcome.report.id}")
            st.caption(f"HTML report: {outcome.report.html_path}")

    _render_review_panel()


def _target(name: str, base_url: str, api_text: str, ui_text: str, authorized: bool, environment: str) -> TargetSite:
    return TargetSite(
        name=name.strip() or "Unnamed target",
        base_url=base_url.strip(),
        api_endpoints=_lines(api_text),
        ui_paths=_lines(ui_text) or ["/"],
        authorized=authorized,
        environment=environment,
    )


def _lines(value: str) -> list[str]:
    return [line.strip() for line in value.splitlines() if line.strip()]


def _render_review_panel() -> None:
    queue = ReviewQueue()
    records = queue.list_records()
    st.subheader("3. Human review")
    if not records:
        st.info("No reports await review.")
        return
    ids = [record["report"]["id"] for record in records]
    selected = st.selectbox("Report", ids)
    record = queue.get(selected)
    st.write(f"Status: **{record['approval_status']}**")
    notes = st.text_input("Review notes", key=f"notes-{selected}")
    c1, c2 = st.columns(2)
    if c1.button("Approve report"):
        queue.approve(selected, notes)
        st.success("Report approved for local delivery preparation.")
    if c2.button("Reject report"):
        queue.reject(selected, notes)
        st.warning("Report rejected.")
    html_path = record["report"].get("html_path")
    if html_path and Path(html_path).exists():
        st.link_button("Open HTML report", f"file://{Path(html_path).resolve()}")


if __name__ == "__main__":
    main()
