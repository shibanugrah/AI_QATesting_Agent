# Product Scope — Phase 1

## First-release promise

A local QA orchestration tool that lets an authorized user select Smoke or API checks, preview the plan, execute only the chosen suite, review artifacts, and approve the final report.

## Implemented now

- Smoke and API suite selection
- Backend test filtering before execution
- CLI plan, run, and dry-run commands
- Streamlit plan preview (optional dependency)
- File-backed HTML reports and a human approval gate
- Safe-only GET/HEAD URL checks and basic private/internal target blocking

## Modeled but not executable yet

- Unit, Integration, E2E, Regression, Accessibility, Visual, Security Baseline
- Repository runners
- Playwright workflows
- LLM-generated tests and semantic retrieval
- Hosted multi-user deployment and background queues

## Non-goals

This release does not offer broad security scanning, arbitrary shell commands, destructive HTTP operations, real email delivery, or autonomous code changes.
