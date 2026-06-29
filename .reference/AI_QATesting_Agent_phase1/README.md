# AI QA Testing Agent — Selective QA Orchestration (Phase 1)

A local, Python-based QA orchestration prototype. An authorized user can select **Smoke** or **API** checks, preview exactly which cases are included, run only those cases, inspect a local HTML report, and require human approval before local delivery preparation.

> This version is deliberately not described as an autonomous AI agent, an LLM test generator, a semantic RAG system, a production platform, or a full end-to-end browser testing suite.

## What works

- Suite-aware cases: `smoke`, `api`, plus modeled future suites
- Backend filtering before execution
- `plan`, `run`, and `--dry-run` CLI commands
- Strict JSON configuration validation (`api_endpoints`, not `api_tests`)
- Safe URL execution boundary: authorization flag, safe GET/HEAD only, and internal/private target blocking
- HTML test reports, file-backed review queue, approval/rejection, and local outbox preparation
- Optional Streamlit plan-preview dashboard

## Supported profiles

| Profile | Status | Notes |
|---|---|---|
| Smoke | Implemented | Fast critical page/API checks |
| API | Implemented | Safe GET/HEAD checks |
| Unit | Modeled | Requires a repository runner |
| Integration | Modeled | Requires repository/staging adapters |
| E2E | Modeled | Requires a Playwright workflow adapter |
| Regression, Accessibility, Visual, Security Baseline | Modeled | Not executable in Phase 1 |

## Architecture

```text
CLI / Streamlit dashboard
        ↓
Config validation + authorization boundary
        ↓
Test generator → test planner → suite filter
        ↓
API runner / UI availability runner
        ↓
HTML report → human review queue → approved local outbox
```

## Quick start

```bash
python -m pytest
python -m qa_agent.cli plan --config examples/demo_smoke.json --suite smoke
python -m qa_agent.cli run --config examples/demo_smoke.json --suite smoke --dry-run
python -m qa_agent.cli run --config examples/demo_smoke.json --suite smoke
```

Select multiple profiles only when both are supported:

```bash
python -m qa_agent.cli plan --config examples/demo_smoke.json --suite smoke --suite api
```

The real URL run needs a network-enabled environment. The included tests use injected runners, so they do not call the internet.

## Review workflow

The run writes:

- `artifacts/reports/<report-id>.html`
- `artifacts/review_queue/<report-id>.json` with `approval_status: pending`

Approve before local delivery preparation:

```bash
python -m qa_agent.cli approve <REPORT_ID> --notes "Reviewed"
python -m qa_agent.cli send-email <REPORT_ID> --to qa@example.com
```

`send-email` creates a local outbox file. It does not send real email.

## Optional dashboard

```bash
pip install -e '.[dashboard]'
streamlit run dashboard/streamlit_app.py
```

## Development

```bash
python -m pytest
```

See [docs/PRODUCT_SCOPE.md](docs/PRODUCT_SCOPE.md), [docs/TEST_PROFILES.md](docs/TEST_PROFILES.md), and [docs/SECURITY_BOUNDARIES.md](docs/SECURITY_BOUNDARIES.md).
