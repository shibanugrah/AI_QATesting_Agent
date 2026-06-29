# AI QA Testing Agent

A **local QA automation scaffold** that runs configured API and UI checks, creates HTML reports, stores lightweight failure history, and requires human approval before report delivery preparation.

> **Current status:** prototype / local development tool. It is not yet a production platform, a full end-to-end testing system, semantic RAG, or an autonomous coding agent.

The product direction is documented in [PRD2.md](PRD2.md): a private, local, Codex-assisted QA learning loop first; selective testing, local QA Memory, MCP, and shared-platform capabilities later.

---

## What works today

- Generate deterministic API checks from configured endpoints.
- Run API checks with HTTP status and optional response-text expectations.
- Run basic UI/page-load checks.
- Optionally use Selenium for browser loading and failure screenshots.
- Produce HTML reports.
- Store reports in a local human-review queue.
- Approve or reject reports before delivery preparation.
- Prepare approved report delivery as a local outbox file.
- Run a basic Streamlit dashboard.
- Run multiple target configurations through the current batch command.
- Store lightweight local failure-memory data for later similarity lookup.

## What does **not** work yet

- Selectable `smoke`, `unit`, `api`, `integration`, `e2e`, or regression suites.
- Repository-aware unit-test execution.
- Real browser user journeys such as login, form submission, checkout, or role-based flows.
- Playwright as the default browser runner.
- Strict Pydantic/JSON-schema configuration validation.
- Test-plan preview or dry-run mode.
- SQLite-backed QA Memory with human-approved learning records.
- Codex hooks, MCP, GitHub Actions integration, or a hosted platform.
- Real email sending; the current MVP writes an outbox file.

Do not describe the project as an autonomous AI QA agent, semantic RAG system, or production-ready platform until those features are implemented and validated.

---

## Safety boundary

Use this tool only against systems you own or are explicitly authorized to test.

The current runner can make requests to a configured URL. Do not point it at private systems, third-party services, or production systems without clear authorization. Do not store credentials in repository configuration files, reports, or artifacts.

---

## Quick start — current implementation

### 1. Clone and create a virtual environment

```bash
git clone https://github.com/shibanugrah/AI_QATesting_Agent.git
cd AI_QATesting_Agent
python -m venv .venv
```

Activate it:

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

```bash
# macOS / Linux
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the current test suite

The current repository documents and uses the standard-library test runner. Pytest standardization is planned in Phase 0 of [PRD2.md](PRD2.md).

```bash
python -m unittest discover -s tests
```

### 4. Create a controlled target configuration

Use `api_endpoints` in new configuration files. The existing `examples/example_site.json` uses an older `api_tests` key and will be corrected as part of Phase 0.

Create `examples/my_local_target.json`:

```json
{
  "name": "My Approved Test Target",
  "base_url": "https://staging.example.com",
  "api_endpoints": ["/api/health"],
  "ui_paths": ["/", "/login"]
}
```

Replace the sample URL with a local, demo, or staging system you own or are authorized to test.

### 5. Run a QA pipeline

```bash
python -m qa_agent.cli run --config examples/my_local_target.json
```

Expected output includes:

- a report ID;
- an HTML report path;
- `Approval status: pending`.

Generated files are stored under:

```text
artifacts/reports/
artifacts/review_queue/
```

### 6. Review, approve, and prepare delivery

```bash
python -m qa_agent.cli approve <REPORT_ID> --notes "Reviewed locally"
python -m qa_agent.cli send-email <REPORT_ID> --to qa@example.com
```

Delivery is blocked until approval. The current MVP writes a prepared message to:

```text
artifacts/outbox/<REPORT_ID>.eml.txt
```

### 7. Optional: start the dashboard

```bash
streamlit run dashboard/streamlit_app.py
```

The current dashboard lets you enter a target, run configured API/UI checks, inspect report counts and analysis, approve or reject a report, prepare approved delivery, and render the generated HTML report.

### 8. Optional: enable Selenium page loading

The default UI runner uses a simple page-load check. To enable the optional Selenium path:

```powershell
pip install selenium
$env:QA_AGENT_REAL_SELENIUM="1"
$env:QA_AGENT_UI_TIMEOUT="20"
$env:QA_AGENT_UI_RETRIES="2"
$env:QA_AGENT_HEADLESS="1"
python -m qa_agent.cli run --config examples/my_local_target.json
```

When Selenium fails, screenshots are written under `artifacts/screenshots/` when available.

### 9. Optional: run a batch

```bash
python -m qa_agent.cli batch --configs examples/my_local_target.json examples/my_local_target.json --parallelism 2
```

**Known limitation:** retry behavior needs correction before it should be relied on for critical batch work. See [PRD2.md](PRD2.md).

---

## Current architecture

```text
CLI / Streamlit dashboard
          ↓
      QA pipeline
 ┌────────┼─────────┐
 │        │         │
Test   API runner  UI runner
Generator            ↓
          Failure analysis + lightweight memory
                         ↓
                   HTML report
                         ↓
              Human review queue
                         ↓
            Approved outbox preparation
```

---

## Codex-first future workflow

The next product stage is local and interactive:

```text
You + personal Codex sign-in
            ↓
    Local repository changes
            ↓
 AI_QATesting_Agent test planner
            ↓
 Selected tests + artifacts + QA Memory
            ↓
  Human-approved lessons for future work
```

The intended workflow is:

1. Start Codex locally in your repository.
2. Ask it to inspect a change and identify the smallest relevant tests.
3. Preview a test plan.
4. Run only selected suites such as smoke or unit tests.
5. Save logs, failures, diffs, screenshots, and rerun results locally.
6. Retrieve similar prior validated cases before asking Codex to repair an issue.
7. Promote a lesson to trusted QA Memory only after a human review and passing validation.

This future workflow will use your interactive personal Codex sign-in locally. It must not reuse personal Codex credentials in CI, a server, a VPS, or background automation.

---

## Planned test profiles

These are target capabilities, not current commands:

| Profile | Purpose | Target mode |
|---|---|---|
| Smoke | Fast critical-path confidence | URL or repository |
| Unit | Isolated code behavior | Repository only |
| API | Endpoint and contract checks | URL or repository |
| Integration | Service and persistence checks | Repository or approved staging |
| E2E | Browser user journeys | URL or repository |
| Regression | Broader stable coverage | URL or repository |
| Accessibility | Basic accessibility checks | URL or repository |
| Visual | Screenshot baseline comparison | URL or repository |
| Security baseline | Safe defensive checks only | Owned/authorized targets |

After Phase 1, commands will follow this pattern:

```bash
python -m qa_agent.cli plan --config examples/demo_smoke.json --suite smoke
python -m qa_agent.cli run --config examples/demo_smoke.json --suite smoke
python -m qa_agent.cli run --config examples/demo_smoke.json --suite smoke --dry-run
```

These commands are documented as a roadmap only. They do not exist in the current codebase.

---

## Roadmap

### Phase 0 — Stabilize

- Standardize on `api_endpoints`.
- Add strict configuration validation.
- Standardize on Pytest.
- Correct or clearly document batch retry behavior.
- Add `AGENTS.md` for local Codex work.

### Phase 1 — Selective orchestration

- Add test suites, `RunRequest`, `TestPlan`, and backend filtering.
- Add plan, run, and dry-run support.
- Add suite selection and plan preview to the dashboard.
- Prove behavior with automated tests.

### Phase 2 — Better execution evidence

- Add repository-aware Pytest execution.
- Add Playwright browser scenarios.
- Add traces, screenshots, console logs, and network artifacts.
- Add richer API assertions.

### Phase 3 — Local QA Memory

- Add SQLite-backed learning records.
- Capture validated test/fix evidence.
- Add review, approval, redaction, and deterministic retrieval.
- Add trusted local Codex hooks only after the CLI workflow is stable.

### Phase 4+ — Semantic retrieval, MCP, and deployment

- Add locally hosted semantic retrieval only after structured memory works.
- Add local MCP tools for the owner’s workflow.
- Add provider-neutral integrations later.
- Containerize and deploy only after the local system has proved useful.

Read [PRD2.md](PRD2.md) for detailed requirements, data models, safety boundaries, acceptance criteria, and the initial Codex build prompt.

---

## Repository documentation

- [PRD2.md](PRD2.md) — product requirements and roadmap.
- `AGENTS.md` — planned repository instructions for Codex and other coding agents.
- `docs/` — planned architecture, test profile, QA Memory, security, Codex workflow, and deployment documents.

---

## License

No license file is currently included. Add an appropriate open-source license before inviting reuse or external contributions.
