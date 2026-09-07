"""Thin local controller/viewer using the same engine API as the CLI."""

import streamlit as st
from qa_engine import Engine, RunRequest


def main():
    st.set_page_config(page_title="QA Engine", layout="wide")
    st.title("QA Engine")
    engine = Engine(st.sidebar.text_input("Data directory", ".qa-engine"))
    project_id = st.text_input("Enrolled project ID")
    profiles = st.multiselect(
        "Profiles (empty uses project inventory and policy)",
        [
            "smoke",
            "api",
            "unit",
            "integration",
            "regression",
            "lint",
            "build",
            "type",
            "browser_e2e",
            "accessibility",
            "security_dependency_scan",
        ],
    )
    dry = st.checkbox("Dry run", value=True)
    if st.button("Run verification", disabled=not project_id):
        try:
            result = engine.run(RunRequest(project_id=project_id, profiles=profiles, dry_run=dry))
            st.session_state["run_id"] = result.run_id
        except (ValueError, KeyError):
            st.error("Check enrollment/configuration")
    run_id = st.text_input("Run ID", value=st.session_state.get("run_id", ""))
    if project_id and run_id:
        try:
            result = engine.get_run(project_id, run_id)
            st.metric("Gate", engine.gate(project_id, run_id).decision)
            st.write("Run status:", result.run_status, "Report review:", result.approval)
            st.dataframe(
                [
                    {"check": c.id, "status": c.status, "mandatory": c.mandatory, "classification": c.classification, "reason": c.reason}
                    for c in result.checks
                ]
            )
            st.json(result.model_dump(mode="json"))
            reviewer = st.text_input("Human reviewer")
            if st.button("Approve report for local export", disabled=not reviewer):
                engine.review_report(project_id, run_id, "APPROVED", reviewer=reviewer)
                st.rerun()
        except (KeyError, ValueError):
            st.error("Run unavailable or evidence invalid")


if __name__ == "__main__":
    main()
