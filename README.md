# QA Engine — Legacy Prototype Baseline

This repository is the **authoritative legacy/prototype baseline** that will be used for the separate QA Engine rebuild.

The future product definition is:

> **QA Engine is an independent software verification layer for humans and AI agents that converts software changes and running applications into reproducible evidence and deterministic quality decisions.**

Core invariant:

> **Builder ≠ Verifier.**

This preparation commit does **not** implement the future QA Engine architecture.

## Authoritative active implementation

Unless a later approved specification changes this, the active prototype source is the code in the repository root, including:

- `qa_agent/` — CLI, pipeline, models, reporting helpers
- `agents/` — current deterministic test generation/failure-analysis helpers
- `executor/` — current API and optional Selenium/page-load runners
- `human_review/` — report review/approval prototype
- `reports/` — HTML report generation
- `rag/` — legacy lightweight failure-history prototype
- `scheduler/` — current batch/job prototype
- `dashboard/` — current Streamlit viewer
- `email/` — current local outbox preparation
- `tests/` — current automated tests
- `examples/` — current example configuration

Historical Phase-1 code, old roadmap material, and saved patch/worktree experiments are **not implementation authority**. Their preservation map is in [`docs/history/README.md`](docs/history/README.md).

## What the current prototype does

- Generates deterministic API and UI/page-load checks from configuration.
- Checks API status and optional response text.
- Runs basic UI/page-load checks; Selenium can be enabled explicitly.
- Captures Selenium failure screenshots when available.
- Produces HTML reports.
- Stores reports in a local review queue.
- Supports approve/reject before local outbox preparation.
- Includes a basic Streamlit dashboard.
- Includes a batch prototype and lightweight failure-history prototype.

## What is not implemented yet

The current baseline is **not** the final QA Engine. It does not yet provide the approved V1 architecture such as repository/change verification, deterministic release gating, project-scoped SQLite QA Memory, Playwright E2E, GitHub PR/SHA verification, the 30 observable checkpoints, or the future Python API.

Do not present roadmap capabilities as working features.

## Quick start — current prototype only

### 1. Create and activate a virtual environment

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
source .venv/bin/activate
```

### 2. Install current runtime dependencies

```bash
pip install -r requirements.txt
```

The standard page-load runner uses the Python standard library. Selenium is optional and is not required for the default test path.

To use the optional real Selenium path:

```bash
pip install selenium
```

### 3. Run the current automated tests

```bash
python -m unittest discover -s tests
```

The current baseline uses `unittest`-compatible tests. A later rebuild may choose different tooling, but this preparation pass does not change the test architecture.

### 4. Run the current example

`examples/example_site.json` uses the active key `api_endpoints`.

```bash
python -m qa_agent.cli run --config examples/example_site.json
```

Only run remote checks against systems you own or are explicitly authorized to test.

### 5. Optional dashboard

```bash
streamlit run dashboard/streamlit_app.py
```

### 6. Optional Selenium mode

```powershell
$env:QA_AGENT_REAL_SELENIUM="1"
python -m qa_agent.cli run --config examples/example_site.json
```

## Locked future direction — context, not implementation

The later QA Engine build is expected to follow these principles:

- deterministic-first verification;
- LLM output is never evidence;
- owner project policy outranks AI planning;
- policy-mandatory checks must execute successfully before a future gate can return PASS;
- 30 checkpoints are an observable execution contract, not a rigid internal pipeline;
- internal orchestration may use a DAG/state machine;
- repository-native capabilities are discovered instead of forcing identical checks on every project;
- Python remains the core;
- the future browser boundary is a small TypeScript Playwright Test worker;
- Chromium only for initial V1 browser execution;
- SQLite + FTS5 before vector retrieval;
- GitHub is first-class and read-only by default;
- project, credential, memory, and baseline isolation are mandatory.

These are architectural constraints for the later build prompt. They are **not claims about current code**.

## Safety

- Test only owned or explicitly authorized targets.
- Do not commit credentials, cookies, tokens, or secrets.
- Do not use the current prototype for destructive or offensive testing.
- Do not treat generated prose or AI suggestions as evidence.

## Historical material

See [`docs/history/README.md`](docs/history/README.md) for the archived PRD and exact commit references for the removed `.reference` Phase-1 bundle, saved patch, and working-tree snapshot.

## License

No license file is currently included. Decide licensing before external/client reuse or inviting outside contributions.
