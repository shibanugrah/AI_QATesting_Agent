# PRD2 — AI_QATesting_Agent

**Version:** 2.0  
**Status:** Build-ready roadmap  
**Primary operating mode:** Private, local, Codex-assisted QA learning loop  
**Repository:** `shibanugrah/AI_QATesting_Agent`

---

## 1. Executive Summary

AI_QATesting_Agent will evolve from a phase-based QA automation scaffold into a **private, local QA orchestration and learning system** for the repository owner’s projects.

The first product is intentionally narrow:

- The owner uses Codex interactively on a local machine, signed in with their personal ChatGPT/Codex account.
- Codex inspects code, changes code, and runs approved local commands.
- AI_QATesting_Agent chooses and runs the requested QA suites, collects artifacts, and creates reviewable learning records.
- Local QA Memory retrieves similar prior failures, validated fixes, and useful test commands before later repair work.
- A human decides whether a lesson is trustworthy before it becomes reusable memory.

The long-term direction is provider-neutral: local MCP tools, integrations for multiple coding agents, GitHub and webhook support, and eventually a shared hosted platform. Those are **not** part of the first release.

This PRD describes the target state while keeping the current repository honest: it has configured API/UI checks, reports, a human review queue, a dashboard, a CLI, lightweight failure-memory concepts, and batch concepts. It does not yet have selectable test suites, real browser workflows, semantic retrieval, Codex integration, or hosted deployment.

---

## 2. Product Vision

> AI_QATesting_Agent is a local QA orchestration and learning tool that helps a developer use Codex to run the right tests, preserve validated debugging knowledge, and improve future repair decisions without requiring an OpenAI API key for the initial interactive workflow.

The product should answer:

1. What is the smallest safe and relevant test set for this change?
2. What failed, and what evidence explains the failure?
3. Has a similar failure happened before?
4. Which prior fixes were actually validated and human-approved?
5. What should Codex inspect or test next?

### First user

A solo developer working on local repositories and approved local, demo, or staging environments.

### Long-term users

Individual developers, QA engineers, small teams, coding-agent workflows, and CI/CD systems.

---

## 3. Problem Statement

Coding agents can make plausible changes quickly, but developers still need to choose tests, understand failures, find prior incidents, and prove a fix is correct. This work repeats across projects:

- Broad test runs waste time when a smoke or unit suite is enough.
- The same configuration and routing failures are rediscovered.
- Logs, screenshots, diffs, and successful fixes are scattered.
- A coding-agent answer may look convincing without being validated.
- Current test output does not become structured, trustworthy future knowledge.

The current project has the foundation for QA execution and reporting, but all configured checks run together and the failure-memory feature is not yet a durable, validated learning system.

---

## 4. Goals

### 4.1 First local release goals

1. Run only selected profiles: `smoke`, `unit`, `api`, `integration`, `e2e`, `regression`, `accessibility`, `visual`, or `security_baseline`.
2. Enforce suite selection in backend logic, not only in the dashboard.
3. Support repository targets and controlled URL/staging targets.
4. Keep Codex interactive and local through the owner’s personal sign-in.
5. Capture commands, exit codes, logs, reports, screenshots, traces, diffs, and rerun results.
6. Store structured learning records locally.
7. Retrieve prior relevant, validated lessons before repair or test planning.
8. Require human approval before a lesson becomes trusted memory and before report delivery actions.
9. Keep first-release state local, inspectable, and portable.
10. Create a clean later path to MCP and provider-neutral integrations.

### 4.2 Success criteria

The first release is successful when it is used across at least three real repositories or controlled demo projects and demonstrates that it:

- filters selected suites correctly;
- produces useful failure artifacts;
- retrieves a relevant past approved lesson in a later similar failure;
- excludes rejected or unvalidated suggestions from trusted retrieval;
- works in the primary interactive workflow without an OpenAI API key.

---

## 5. Non-Goals for the First Release

The first release will not provide:

- a public SaaS product;
- multi-user accounts, billing, or tenancy;
- automatic PR merging or production deployment;
- unattended Codex automation using a personal ChatGPT/Codex sign-in;
- copying, committing, sharing, or exporting Codex authentication data;
- arbitrary shell commands from dashboard, JSON, or YAML input;
- offensive security scanning or destructive testing;
- claims of LLM-generated tests, semantic RAG, or production readiness before implementation proves them;
- a replacement for existing CI/CD services.

---

## 6. Confirmed Current State

### Already present

- Configured API and UI test generation.
- API execution with status-code and optional response-text checks.
- Basic UI/page-load checks and optional Selenium mode.
- Rule-based failure analysis.
- HTML reports.
- File-backed human report review.
- Report approval/rejection and outbox-file delivery preparation.
- CLI, Streamlit dashboard, local failure-memory concept, and batch concepts.

### Not yet present

- Test tags or selectable suites.
- Repository-aware unit-test execution.
- User-journey E2E tests.
- Playwright default browser execution.
- Strict configuration validation.
- Test-plan preview or dry run.
- Durable database-backed jobs or learning records.
- Semantic embeddings/vector retrieval.
- Codex hooks, MCP, or agent adapters.
- Containerized deployment.

### Immediate corrections

1. Standardize configuration on `api_endpoints`; reject `api_tests` and unknown fields.
2. Standardize internal testing on Pytest; stop documenting conflicting test runners.
3. Fix or temporarily disable the current batch retry behavior until retries run reliably.
4. Add authorization and SSRF safeguards before the URL runner is made shareable or deployed.

---

## 7. Personal Codex Operating Model

### 7.1 First-release boundary

The owner starts Codex from the local repository directory, signs in interactively with their personal account, and asks Codex to inspect, implement, test, and explain work.

AI_QATesting_Agent itself does not authenticate to OpenAI in this phase. It runs local test commands, stores artifacts, manages QA Memory, and supports review decisions.

```text
Developer → interactive Codex session → approved local code and test commands
                       ↓
            AI_QATesting_Agent local tools
                       ↓
      local artifacts + local QA Memory + human review
```

### 7.2 Security boundary

Do not run Codex unattended in CI, a VPS, a background server, or a public dashboard by reusing personal login credentials. Do not copy or commit Codex authentication files. Treat them like passwords.

### 7.3 Approved local use

- Start Codex from the repository directory.
- Use `AGENTS.md` for persistent repository rules.
- Ask Codex to run the smallest relevant test suite first.
- Use reviewed local hooks only after the basic CLI workflow works.
- Capture validated outcomes through local project scripts.

---

## 8. Functional Requirements

### FR-1: Test profiles

The system must define these suites:

| Suite | Purpose | Allowed targets |
|---|---|---|
| `smoke` | Fast critical-path confidence | URL, repository |
| `unit` | Isolated code behavior | Repository only |
| `api` | Endpoint and contract checks | URL, repository |
| `integration` | Services, databases, queues, mocks | Repository, approved staging |
| `e2e` | Browser user journeys | URL, repository |
| `regression` | Broader stable coverage | URL, repository |
| `accessibility` | Basic accessibility checks | URL, repository |
| `visual` | Screenshot baseline comparison | URL, repository |
| `security_baseline` | Safe defensive checks only | Owned/authorized targets |

Requirements:

- Every test case has a required `suite`.
- `selected_suites=["smoke"]` executes only smoke cases.
- Unsupported combinations are rejected before execution. For example, a URL-only target cannot run `unit`.
- A test plan lists included and excluded cases with reasons.
- Automated tests prove suite filtering works.

### FR-2: Test planning and dry runs

A test plan must include:

- selected suites;
- included and excluded test cases;
- target mode and environment;
- missing prerequisites or required secrets;
- policy warnings;
- expected adapters such as Pytest, API runner, and Playwright.

A dry run must not contact a target, start a browser, execute test commands, or modify project files.

### FR-3: Target modes

1. **Repository target:** a local checked-out codebase. Used for unit, integration, lint, and repository-defined E2E tests.
2. **URL/staging target:** a controlled web or API environment. Used for smoke, API, browser, accessibility, visual, and safe approved security-baseline checks.

Every remote target requires confirmation that the user owns or is authorized to test it.

### FR-4: Execution adapters

Use adapters rather than placing all test logic in one pipeline:

- `PytestExecutor` for repository unit, integration, and regression suites.
- `ApiExecutor` for safe HTTP requests, status/text/JSON assertions, headers, timeouts, and redaction.
- `PlaywrightExecutor` for browser workflows and artifacts; this becomes the target default browser adapter.
- `AccessibilityExecutor` and `VisualExecutor` later.

Dashboard and API layers must not run browsers directly. Browser work runs in a controlled local worker process first and isolated workers later.

### FR-5: Codex-guided local workflow

Add `AGENTS.md` containing:

- project purpose and architecture rules;
- required quality commands;
- rules for secrets and authorized targets;
- smallest-relevant-suite-first policy;
- requirement to capture failed tests and approved outcomes in QA Memory.

Codex remains an interactive developer tool, not a mandatory runtime dependency.

### FR-6: QA Memory and learning records

The first durable version uses SQLite. Each record must retain structured metadata and links to evidence:

```text
record_id
project_id
repository_identifier
created_at
source
suite
command_run
commit_sha_or_diff_summary
environment
failure_signature
symptom_summary
root_cause_summary
proposed_fix_summary
validation_command
validation_result
human_review_status
confidence
artifact_paths
redaction_status
```

Record states:

- `draft`: created from a run or manual input;
- `validated`: diagnosis or fix was rerun and verified;
- `approved`: a human accepted it as reusable;
- `rejected`: retained for audit but excluded from normal retrieval;
- `expired`: excluded when no longer relevant.

Only `approved`, and optionally `validated`, records may appear as high-confidence guidance.

### FR-7: Retrieval strategy

Phase 1 retrieval is structured and deterministic:

- match project, language/framework, suite, exception class, route, test name, or failure type;
- prefer matching environments and recent approved cases;
- always show why a record matched.

Phase 2 adds local semantic retrieval using a local embedding model plus Chroma or FAISS. SQLite remains the source of truth for metadata, state, and approval. Until semantic retrieval is implemented and measured, call this feature **QA Memory**, not RAG.

### FR-8: Human review

- Reports remain pending before delivery actions.
- Learning records remain draft or validated before promotion.
- The owner can approve, reject, edit, redact, or expire a lesson.
- Decisions are auditable.
- Rejected lessons cannot appear in default Codex context.

### FR-9: Artifacts

Store, when available:

- command and exit code;
- stdout and stderr;
- HTML report;
- JUnit XML or structured test output;
- screenshots, traces, video, console output, and network failures for browser tests;
- Git diff summary;
- retrieved memory record IDs.

Phase 1 keeps artifacts in `artifacts/` and references relative paths from SQLite.

### FR-10: CLI and dashboard

The CLI must support plan, run, dry-run, memory search, and memory review. Target commands after implementation:

```bash
python -m qa_agent.cli plan --config examples/demo_smoke.json --suite smoke
python -m qa_agent.cli run --config examples/demo_smoke.json --suite smoke
python -m qa_agent.cli run --config examples/demo_smoke.json --suite smoke --dry-run
python -m qa_agent.cli memory search --query "login timeout after auth redirect"
python -m qa_agent.cli memory review <RECORD_ID> --approve
```

The dashboard must add:

- repository/URL target mode;
- test-suite multiselect;
- environment selector;
- remote-target authorization confirmation;
- Preview Test Plan and Run Selected Tests actions;
- included/excluded test display;
- artifact and QA Memory review panels;
- existing report approval controls.

### FR-11: Configuration validation

Use Pydantic or equivalent strict validation:

- use `api_endpoints`, not `api_tests`;
- reject unknown fields;
- validate URL scheme, hostname, paths, and suite values;
- block path traversal;
- reject dangerous methods unless an approved policy permits them;
- return actionable errors instead of ignoring invalid configuration.

### FR-12: Security rules

- Run only against owned or authorized systems.
- In shared/deployed modes, block loopback, private, link-local, and cloud metadata targets.
- Cap request count, redirects, response bytes, execution time, and retries.
- Default remote API checks to safe methods such as `GET` and `HEAD`.
- Keep secrets in local environment variables or a local secret store.
- Redact likely secrets before memory promotion.
- Never accept arbitrary shell commands through user configuration or dashboard input.
- Require human approval before destructive or release-affecting actions.

---

## 9. Architecture

```text
Owner + local interactive Codex session
                 │
                 ▼
        AGENTS.md + local scripts
                 │
                 ▼
      AI_QATesting_Agent Orchestrator
        ├── Config validator
        ├── Test planner
        ├── Policy engine
        ├── QA Memory service
        ├── Report service
        └── Human review service
                 │
                 ▼
          Execution adapters
   ┌─────────────┼─────────────┐
   │             │             │
Pytest       API runner    Playwright
   │             │             │
   └─────────────┴─────────────┘
                 │
                 ▼
     Local artifacts + SQLite QA Memory
                 │
                 ▼
   CLI / Streamlit dashboard / future MCP
```

Target package direction:

```text
qa_agent/
├── domain/          # run request, test plan, learning record models
├── services/        # planner, policy, QA Memory, reports, redaction
├── executors/       # pytest, API, Playwright
├── storage/         # SQLite repositories and migrations
└── cli.py
```

---

## 10. Core Data Models

```python
@dataclass(slots=True)
class RunRequest:
    target_mode: str             # repository | url
    target_ref: str              # local path or approved base URL
    selected_suites: list[str]
    environment: str = "local"
    browser: str = "chromium"
    fail_fast: bool = False
    dry_run: bool = False
    authorized_target: bool = False

@dataclass(slots=True)
class TestCase:
    id: str
    name: str
    suite: str
    kind: str                    # api | ui | repository
    target: str
    priority: str = "medium"
    tags: list[str] = field(default_factory=list)
    adapter: str = "api"

@dataclass(slots=True)
class LearningRecord:
    id: str
    project_id: str
    failure_signature: str
    symptom_summary: str
    root_cause_summary: str
    proposed_fix_summary: str
    validation_result: str
    review_status: str           # draft | validated | approved | rejected | expired
    artifact_paths: list[str]
```

---

## 11. Quality Requirements

### Reliability

- A failed test creates a result record even when report generation fails.
- A QA Memory write failure never hides the original test result.
- Retries are bounded and visible.

### Performance

- Normal local dry-run plans should return in under two seconds.
- Smoke suites should use a configurable budget; initial default target is under five minutes.
- Structured local retrieval should return relevant top results quickly for normal project history.

### Explainability and privacy

- Explain every selection and exclusion decision.
- Show why each memory record matched.
- Keep local-first data handling.
- Never write personal Codex credentials into files, logs, artifacts, prompts, or CI.

---

## 12. Phased Roadmap

### Phase 0 — Stabilize the existing scaffold

- Correct `api_endpoints` configuration mismatch.
- Introduce strict validation.
- Standardize on Pytest.
- Repair or document retry limitations.
- Update README truthfully.

### Phase 1 — Selective test orchestration

- Add suites, `RunRequest`, `TestPlan`, and backend filtering.
- Add `plan`, `run`, and `--dry-run` commands.
- Update dashboard with target mode, suite selection, and plan preview.
- Add test coverage for validation, filtering, dry runs, and unsupported combinations.

### Phase 2 — Credible execution adapters

- Add repository Pytest execution.
- Replace Selenium-first design with Playwright.
- Add declarative browser scenario steps.
- Capture screenshots, traces, console logs, and network evidence.
- Add improved API assertions.

### Phase 3 — Local Codex QA learning loop

- Add `AGENTS.md`.
- Add SQLite QA Memory and draft learning records.
- Capture command/test/fix evidence.
- Add human review, approval, redaction, and deterministic retrieval.
- Add reviewed local Codex hooks only after the CLI workflow is stable.

### Phase 4 — Local semantic retrieval

- Add local embeddings and Chroma or FAISS.
- Evaluate retrieval quality with labeled cases.
- Keep approval state and metadata in SQLite.

### Phase 5 — Integration and deployment

- Add a local MCP server for the owner’s workflow.
- Add generic agent adapters, webhook/GitHub support, and Dockerized staging.
- Use service-grade authentication for automation; never use personal Codex credentials in CI or servers.

---

## 13. Acceptance Criteria

### Phase 0

- `api_tests` fails with a clear validation error.
- `api_endpoints` works.
- Documentation identifies one supported test runner.
- Retry behavior is correct or clearly disabled.

### Phase 1

- `--suite smoke` executes no non-smoke tests.
- Dry-run makes no network, browser, shell, or target-changing action.
- URL-only targets reject `unit` with a clear error.
- Dashboard previews included and excluded tests.
- Planner behavior has automated tests.

### Phase 2

- Browser scenarios support navigation, input, click, visible-text, and URL assertions.
- Browser failures create screenshot and trace artifacts.
- API checks support headers and JSON assertions.

### Phase 3

- Test output creates a draft learning record.
- Rejected records never appear in default retrieval.
- Approved records include validation evidence and review metadata.
- Redaction occurs before promotion.
- Codex is guided by `AGENTS.md` without an API key in the interactive local workflow.

### Phase 4+

- Semantic retrieval is evaluated against labeled examples.
- MCP requests are bounded, authenticated, and audited.
- Hosted deployment uses service authentication rather than personal credentials.

---

## 14. Risks and Controls

| Risk | Control |
|---|---|
| Memory becomes noisy | Retrieve approved/validated lessons by default; support expiry and rejection. |
| Codex proposes a wrong fix | Require targeted tests, reruns, and human approval before memory promotion. |
| Unsafe target access | Authorization confirmation, policy checks, allowlists, and network restrictions in shared modes. |
| Secrets leak into records | Environment-based secrets, redaction, and no secret values in config or memory. |
| Browser tests are flaky | Stable `data-testid` selectors, trace artifacts, and narrow retry policies. |
| Personal login exposure | Keep Codex authentication local and never commit, share, or automate it in servers/CI. |
| Overbuilding too early | Prove the local workflow across real projects before MCP or SaaS work. |

---

## 15. Future Deployment Strategy

### Stage A — Local only

CLI, Streamlit, SQLite, local artifacts, and interactive personal Codex use. No hosted service and no API key requirement for the core workflow.

### Stage B — Private staging

Docker Compose, FastAPI, PostgreSQL, Redis, object storage, isolated Pytest/Playwright workers, authentication, and audit logging.

### Stage C — Shared platform

Multi-project tenancy, role-based access, generic webhooks/GitHub integration, MCP, and service-level authentication for automated workflows. Personal Codex credentials never run in servers, CI, or worker processes.

Do not move to Kubernetes until containerized staging has real load, reliability, and multi-worker needs.

---

## 16. Initial Codex Build Prompt

```text
Read PRD2.md and AGENTS.md before making changes.

Work only on Phase 0 and Phase 1 of PRD2 for AI_QATesting_Agent.

Goals:
1. Fix configuration validation and standardize on api_endpoints.
2. Standardize testing on pytest.
3. Add test-suite support, RunRequest, TestPlan, and backend filtering.
4. Add CLI plan/run/dry-run commands with repeated --suite arguments.
5. Update Streamlit so users can select target mode and test suites, preview a plan,
   and see included/excluded tests.
6. Preserve existing human report-review behavior.
7. Add tests for validation, suite filtering, unsupported target/suite combinations,
   and dry-run behavior.

Constraints:
- Do not add an OpenAI API key requirement.
- Do not build MCP, server deployment, semantic retrieval, or public accounts yet.
- Do not permit arbitrary shell commands from config or dashboard inputs.
- Do not claim features that are not implemented.
- Keep new public functions typed.
- Run the full test suite and report exact results, changed files, and known limitations.
```
