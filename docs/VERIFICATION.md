# QA Engine V1 final verification

Verification date: 2026-09-07. This report describes the implementation reconciled onto the prepared baseline, not the interrupted session's earlier results.

## A. Executive implementation verdict

**COMPLETE WITH EXTERNAL VALIDATION PENDING** for the authorized local V1 scope. The engine independently executes enrolled repository/API/browser checks, retains reproducible observations, and applies a deterministic policy gate. Controlled fixture evidence does not establish external project success or hosted CI success.

## B. Architecture delivered

Python owns strict contracts, enrollment, policy, discovery/planning, subprocess/HTTP authorization, run state, retries/classification, evidence, fix verification, SQLite memory, reports, and gate evaluation. The small TypeScript Playwright Test worker executes Chromium journeys and returns versioned observations. It contains no project-policy resolver, release gate, memory, AI planner, or GitHub business logic.

The internal implementation uses durable state transitions and dependency barriers between grouped capabilities. It does not implement thirty independent sequential business functions. Checks sharing a checkpoint preserve separate identities and attempts. Execution within one mutable checkout is sequential; separate runs use independent evidence namespaces and SQLite connections.

Caller context is inert. Advisory additions can expand a plan; they cannot remove the mandatory policy floor. Builder assertions, AI text, and external CI colors cannot certify a result.

## C. Major repository changes and preparation integrity

- Added `qa_engine/`: typed domain, state machine, planning, native/API/browser adapters, safe transport, evidence, deterministic gate, reports, CLI/Python API, SQLite migration and FTS5 memory.
- Added `browser_worker/`: locked TypeScript/Playwright/axe dependencies, JSON protocol, journey executor and machine reporter.
- Added controlled fixtures, 30 acceptance cases, 44 control cases, three live browser feature cases, clean-wheel and live-scanner verification helpers.
- Replaced the dashboard with a thin controller. The old CLI forwards to the engine; the prototype pipeline raises an explicit retirement error. Other baseline prototype source remains excluded from the installed product and is covered only by eight compatibility tests.
- Added packaging, owner-enrollment examples, a read-only GitHub workflow, architecture documentation and this report.

The authoritative base is **`0ebf0415c2e75319e195362b994326712ee0d51b`**. `git merge-base --is-ancestor` confirms that it is an ancestor of the implementation branch. Fetch confirmed `origin/main` at that exact SHA.

The final tracked tree contains none of `.reference/AI_QATesting_Agent_phase1/`, `ai-qa-before-commit-split.patch`, `ai-qa-working-tree-status.txt`, or root `PRD2.md`. Empty ignored reference directories left by checkout were inspected and removed. `docs/history/` and the prepared `examples/example_site.json` remain identical to the prepared baseline. AGENTS now describes V1, not Phase 1. The separate untracked nested `AI_QATesting_Agent/` snapshot was neither modified nor committed.

Every changed implementation file and the final diff were reviewed. No runtime SQLite DB, screenshots, traces, test output, virtual environment, Node modules, credentials or machine-specific implementation paths are tracked. Recovery material is local only.

## D. Thirty observable checkpoints

All 30 versioned checkpoints exist in `qa_engine/stages.py` and are persisted with transitions, timestamps, status/reason, policy and evidence fields. The complete checkpoint-to-responsibility table is in [ARCHITECTURE.md](ARCHITECTURE.md#orchestration-decision). Acceptance scenario 2 verifies all thirty records. Checkpoint 23 is explicitly `SKIPPED / CAPABILITY_NOT_IN_V1_POLICY`. Missing capabilities and failed dependencies are represented without silently becoming successful execution.

## E. Repository-native capabilities

Discovery reads Pytest configuration/markers, Ruff/Mypy configuration, Python build metadata, named npm scripts and scanner readiness. Commands also require owner allowlist membership. API and journey inventory comes from enrolled configuration. Required but unavailable/profile-filtered work prevents PASS. Conservative change rules add requirements; no unsupported minimal-test-set claim is made.

The mixed-project regression executes both approved Python and npm unit suites: a passing backend cannot hide a failing frontend. Unit, integration and regression are distinct selections. This repository marks its acceptance/browser suites as integration tests; the workflow runs the full suite separately before its native unit/lint/build self-gate.

## F. Browser verification

Live Playwright Test Chromium execution was repeated after reconciliation. Protocol v1 binds request, project, environment, journey and complete viewport coverage. Desktop/mobile login assertions, intentional login failure, screenshots, sanitized traces, console errors, failed requests, forbidden redirect blocking, and fresh-context authentication isolation passed their assertions. Live axe tests cover both a clean fixture and an intentional missing-label violation.

Python authorizes browser HTTP through a per-attempt broker. Service workers/WebSockets are blocked. Dedicated credentials are ephemeral; no reusable browser storage state is retained. Trace inspection confirms password and session-cookie canaries are absent, including header name/value pairs. The tests invoke the actual worker `playwright test --config ...`; a standalone `npm test` without a broker request is not a supported invocation.

## G. Security verification

Passed controls cover URL parsing, host/port policy, mixed public/private DNS, loopback opt-in, private/metadata/multicast denial before connect, redirects, request/response budgets, project credential binding, process output/time limits, namespace traversal, and evidence integrity. The HTTP/1.0 fixtures exercise bounded response reading while preserving ownership of the pinned socket.

Native execution uses fixed command IDs and argv with `shell=False`, a restricted environment and owner authorization. Windows Job Objects passed orphan-child termination tests. Native project scripts/plugins still execute trusted repository code; this is not an adversarial-code sandbox.

Secret canaries were checked in persisted results, reports, artifacts and SQLite; trace header/body sanitization has a dedicated regression. Screenshots mask inputs and owner-marked private elements. Security adapters are discovered and policy-selected. A separate live `pip-audit` run found **10 vulnerabilities** in the intentionally vulnerable `urllib3==1.26.5` requirement and produced the expected engine **FAIL**, without installing that vulnerable dependency.

## H. QA Memory verification

SQLite migration 1 contains projects, repositories, environments, runs, checkpoints/events, checks/attempts, artifacts, findings, incidents, memory and reviews. Foreign keys, schema versioning, canonical-result hashes and project-qualified reads are exercised. FTS5 retrieval joins back to relational project/trust/expiry/policy filters.

Actual failures become OBSERVED or REPRODUCED; original-check and regression success permits FIX_VALIDATED; explicit human review permits APPROVED. Unapproved, stale, expired, rejected, policy-incompatible and cross-project records are excluded. Retrieval rechecks original/fix evidence. Fingerprints normalize volatile details and are versioned similarity identifiers, not claims of identical root cause. Report approval is separate from memory approval and cannot override a gate.

## I. GitHub verification

Local tests verify exact checked-out base/head and PR metadata binding, mismatch rejection, `contents: read` / `pull-requests: read`, no write permissions or `pull_request_target`, and inability of a green/skipped CI claim to override mandatory checks. Checkout credentials are not persisted. The workflow runs on owner main pushes or explicit dispatch; it uploads evidence and a job summary.

Hosted GitHub Actions execution: **NOT REVERIFIED**. Publishing status is recorded in section N. The product does not automatically post PR comments, merge, or deploy.

## J. Definitive 30-scenario acceptance table

The table below is generated from the post-rebase harness JUnit, not inferred from implementation claims. Scenario 20's absence assertion executed successfully; the capability itself remains outside V1. Scenario 25's deterministic protocol fixture and separate live scanner are distinguished. Scenario 30 uses controlled projects only.

| # | Scenario | Status | Evidence |
|---|---|---|---|
| 01 | installable package and schema | PASS | [test_01_installable_package_and_schema](../artifacts/acceptance/4eace24d-63ce-4609-b969-966e4cb99f46/junit.xml) |
| 02 | known good repository | PASS | [test_02_known_good_repository](../artifacts/acceptance/4eace24d-63ce-4609-b969-966e4cb99f46/junit.xml) |
| 03 | unit regression | PASS | [test_03_unit_regression](../artifacts/acceptance/4eace24d-63ce-4609-b969-966e4cb99f46/junit.xml) |
| 04 | native quality failure | PASS | [test_04_native_quality_failure](../artifacts/acceptance/4eace24d-63ce-4609-b969-966e4cb99f46/junit.xml) |
| 05 | api regression | PASS | [test_05_api_regression](../artifacts/acceptance/4eace24d-63ce-4609-b969-966e4cb99f46/junit.xml) |
| 06 | broken login evidence | PASS | [test_06_broken_login_evidence](../artifacts/acceptance/4eace24d-63ce-4609-b969-966e4cb99f46/junit.xml) |
| 07 | browser console network | PASS | [test_07_browser_console_network](../artifacts/acceptance/4eace24d-63ce-4609-b969-966e4cb99f46/junit.xml) |
| 08 | forbidden target before request | PASS | [test_08_forbidden_target_before_request](../artifacts/acceptance/4eace24d-63ce-4609-b969-966e4cb99f46/junit.xml) |
| 09 | redirect forbidden | PASS | [test_09_redirect_forbidden](../artifacts/acceptance/4eace24d-63ce-4609-b969-966e4cb99f46/junit.xml) |
| 10 | dry run no execution | PASS | [test_10_dry_run_no_execution](../artifacts/acceptance/4eace24d-63ce-4609-b969-966e4cb99f46/junit.xml) |
| 11 | secret canary | PASS | [test_11_secret_canary](../artifacts/acceptance/4eace24d-63ce-4609-b969-966e4cb99f46/junit.xml) |
| 12 | flaky never clean pass | PASS | [test_12_flaky_never_clean_pass](../artifacts/acceptance/4eace24d-63ce-4609-b969-966e4cb99f46/junit.xml) |
| 13 | infrastructure classification | PASS | [test_13_infrastructure_classification](../artifacts/acceptance/4eace24d-63ce-4609-b969-966e4cb99f46/junit.xml) |
| 14 | fix original check | PASS | [test_14_fix_original_check](../artifacts/acceptance/4eace24d-63ce-4609-b969-966e4cb99f46/junit.xml) |
| 15 | fix regression floor | PASS | [test_15_fix_regression_floor](../artifacts/acceptance/4eace24d-63ce-4609-b969-966e4cb99f46/junit.xml) |
| 16 | approved incident retrieval | PASS | [test_16_approved_incident_retrieval](../artifacts/acceptance/4eace24d-63ce-4609-b969-966e4cb99f46/junit.xml) |
| 17 | untrusted memory excluded | PASS | [test_17_untrusted_memory_excluded](../artifacts/acceptance/4eace24d-63ce-4609-b969-966e4cb99f46/junit.xml) |
| 18 | cross project memory | PASS | [test_18_cross_project_memory](../artifacts/acceptance/4eace24d-63ce-4609-b969-966e4cb99f46/junit.xml) |
| 19 | browser auth isolation | PASS | [test_19_browser_auth_isolation](../artifacts/acceptance/4eace24d-63ce-4609-b969-966e4cb99f46/junit.xml) |
| 20 | no visual baseline namespace | NOT APPLICABLE | [test_20_no_visual_baseline_namespace](../artifacts/acceptance/4eace24d-63ce-4609-b969-966e4cb99f46/junit.xml) |
| 21 | mandatory unavailable | PASS | [test_21_mandatory_unavailable](../artifacts/acceptance/4eace24d-63ce-4609-b969-966e4cb99f46/junit.xml) |
| 22 | builder claim ignored | PASS | [test_22_builder_claim_ignored](../artifacts/acceptance/4eace24d-63ce-4609-b969-966e4cb99f46/junit.xml) |
| 23 | interrupted run durable | PASS | [test_23_interrupted_run_durable](../artifacts/acceptance/4eace24d-63ce-4609-b969-966e4cb99f46/junit.xml) |
| 24 | artifact tampering | PASS | [test_24_artifact_tampering](../artifacts/acceptance/4eace24d-63ce-4609-b969-966e4cb99f46/junit.xml) |
| 25 | dependency scanner fixture | PASS | [test_25_dependency_scanner_fixture](../artifacts/acceptance/4eace24d-63ce-4609-b969-966e4cb99f46/junit.xml) |
| 26 | github sha binding | PASS | [test_26_github_sha_binding](../artifacts/acceptance/4eace24d-63ce-4609-b969-966e4cb99f46/junit.xml) |
| 27 | workflow permissions | PASS | [test_27_workflow_permissions](../artifacts/acceptance/4eace24d-63ce-4609-b969-966e4cb99f46/junit.xml) |
| 28 | github green cannot override | PASS | [test_28_github_green_cannot_override](../artifacts/acceptance/4eace24d-63ce-4609-b969-966e4cb99f46/junit.xml) |
| 29 | memory validation approval | PASS | [test_29_memory_validation_approval](../artifacts/acceptance/4eace24d-63ce-4609-b969-966e4cb99f46/junit.xml) |
| 30 | repeatable pilot harness | PASS | [test_30_repeatable_pilot_harness](../artifacts/acceptance/4eace24d-63ce-4609-b969-966e4cb99f46/junit.xml) |

## K. Automated tests and commands

Environment: Windows, Python 3.12.5, Node 22.23.0, Playwright Test 1.58.2; Chromium only.

| Verification | Final result |
|---|---|
| Full Pytest | 85 passed, 0 failed, 0 skipped; five pre-existing prototype dataclass collection warnings |
| Dedicated acceptance harness | 30 test functions passed; 29 scenario PASS, one NOT APPLICABLE |
| Fresh-venv wheel controls | 44 passed, 0 failed, 0 skipped |
| Ruff lint / formatting | PASS / 27 selected Python files formatted |
| Compile/import sanity | PASS |
| npm locked dependency install | PASS; zero reported npm vulnerabilities |
| TypeScript strict typecheck | PASS |
| Live dependency scanner | PASS: expected FAIL gate, 10 fixture vulnerabilities |
| Streamlit AppTest | PASS: render, enrollment input, dry run and NOT_EVALUATED display |
| Clean-checkout self-gate | PASS: actual native lint, package build and 52 unit/compatibility tests |
| Installed CLI outside checkout | PASS; import resolved to fresh venv site-packages |

Commands executed from the root unless stated otherwise:

```text
python -m compileall -q qa_engine browser_worker
python -m ruff check .
python -m ruff format --check qa_engine tests/test_engine_controls.py tests/test_engine_acceptance.py tests/test_browser_features.py tests/engine_fixtures.py tools dashboard/streamlit_app.py
npm ci --prefix browser_worker
npm run typecheck --prefix browser_worker
python -m pytest -q --cov=qa_engine --cov-report=xml:artifacts/coverage.xml --junitxml=artifacts/engine-tests.xml --basetemp=artifacts/post-rebase-suite
python tools/verify_clean_install.py
python -m tools.verify_live_scanner
python -m qa_engine.acceptance --output artifacts/acceptance
python -m pytest --collect-only -q -m "not integration and not regression"
git diff origin/main --check
git merge-base --is-ancestor 0ebf0415c2e75319e195362b994326712ee0d51b HEAD
```

The clean-install helper records exact build/venv/pip/outside-checkout Pytest argv in its result JSON. The installed `qa.exe --help` and Python import path were also checked from its outside-checkout directory. No Python type checker is configured for this product; Ruff and TypeScript checks are reported separately.

The first live-scanner invocation used a direct script path and failed to import the fixture package; the documented module invocation above passed. AppTest initially exceeded its default three-second wait under concurrent verification; rerunning with a 30-second wait passed. Neither unsuccessful invocation is counted as a passed run. No implementation test assertions were weakened.

Post-rebase statement coverage: **82.36%** (1,419 / 1,723 lines). Engine 92.17%, planning 98.08%, storage 96.06%, security 87.96%, gate 87.18%. Coverage is not a proof of correctness; subprocess CLI/harness coverage is incomplete.

Evidence retained locally (runtime artifacts are intentionally ignored by Git):

- [Full-suite JUnit](../artifacts/engine-tests.xml), [coverage XML](../artifacts/coverage.xml).
- [Acceptance manifest](../artifacts/acceptance/results.json), [harness JUnit](../artifacts/acceptance/4eace24d-63ce-4609-b969-966e4cb99f46/junit.xml); fixture repositories, SQLite databases, screenshots and traces remain beside that JUnit.
- [Fresh-wheel verification](../artifacts/clean-install/13a0f44e-e41f-45ba-8b8c-da3c25501313/result.json), including exact commands and 44-test JUnit.
- [Live scanner result](../artifacts/live-scanner/3a00a905-3279-4c56-8d9e-46f37d49f386/result.json): run `5afb06ae-339a-4cba-b450-c9fd51d46c11`.
- [Viewer result](../artifacts/viewer-post-rebase/result.json); AppTest script is `artifacts/check_viewer.py`, run with the previously installed Streamlit test environment against current root source.


A fresh local clone of the implementation commit ran the actual configured self-gate:

```text
git clone --local --no-hardlinks --single-branch --branch feat/qa-engine-v1 . artifacts/self-verification-checkout
python -m qa_engine --data-dir artifacts/self-verification-data enroll artifacts/self-verification-checkout/.github/qa-project.json
python -m qa_engine --data-dir artifacts/self-verification-data run qa-engine-self --profile unit --profile lint --profile build
```

[Self-gate result](../artifacts/self-verification-result.json): run `31e0b032-b017-4326-a5bd-2b069c8994b8`, exact head `dca2211941e075980ef21c9cdade7f1fc9eefdbe`, PASS. Its native unit JUnit contains 52 executed tests; acceptance/browser integration tests remain separately verified by the full suite and harness.

Regression coverage retained: SQLite insertion/schema consistency; HTTP/1.0 bounded reading; Windows clean/dirty Git snapshots; trace header-pair redaction; auth isolation; deleted/replaced original test rejection; mandatory skipped suites; canonical/result/artifact tampering; preview/dry-run redaction; Unix npm layout and Windows execution; Windows orphan cleanup; mixed backend/frontend checks.

## L. Known limitations

- External owner-project pilots and hosted Linux GitHub Actions are not verified by these local runs. Unix npm discovery is tested with a modeled layout; Windows is the actual execution platform.
- Owner enrollment/review are trusted local operator actions, not a multi-user identity service. Native code is not sandboxed, and hashes do not resist an administrator rewriting the whole evidence store.
- Browser evidence intentionally omits trace bodies/DOM snapshots. Private pixels in canvas/images require owner masking. Automated axe results do not establish full accessibility compliance.
- Abruptly terminated runs require an explicit rerun. Artifact retention deadlines are recorded, but automatic disk purging is not implemented.
- Original-test AST binding is implemented for Pytest; other native tools use command-check granularity. Impact selection is conservative.
- Visual regression, other browsers, production execution, AI generation/vector memory, automatic repair/merge/deployment and external report delivery are outside this V1 scope.

## M. External pilot readiness

Ready for separately authorized owner-project pilots with reviewed enrollment policy and dedicated test accounts. Real external three-project pilots: **NOT REVERIFIED / NOT YET EXECUTED**. The Python, mixed and browser projects in scenario 30 are controlled fixtures and are not commercial or field evidence.

## N. Git state and publication

Branch: `feat/qa-engine-v1`.

Implementation commit: `dca2211941e075980ef21c9cdade7f1fc9eefdbe` â€” `feat: build deterministic QA Engine V1`.

Parent/prepared baseline: `0ebf0415c2e75319e195362b994326712ee0d51b`.

The original staged and unstaged work was preserved in local recovery commit `253feb6` on `recovery/qa-engine-before-baseline` and `.git/qa-engine-recovery.patch` before rebase. The feature history has a clean implementation commit rather than the recovery/WIP message. Neither main nor shared history was rewritten. A separate documentation commit records this report.

Normal push to `origin/feat/qa-engine-v1` succeeded using Git's configured credential path even though `gh auth status` reports no CLI login. The connected GitHub integration created [PR #1](https://github.com/shibanugrah/AI_QATesting_Agent/pull/1), targeting main at the exact prepared baseline. The PR remains open and unmerged; no force-push was used. The documentation commit is published on the same branch.

Final intended working-tree status: no tracked modifications; only the pre-existing untracked nested `AI_QATesting_Agent/` snapshot remains. Runtime verification outputs are ignored. The recovery branch is local and was not pushed.

## O. Final invariant verification

| Invariant | Verified behavior |
|---|---|
| Builder â‰  Verifier | Engine executes checks independently; builder-claim acceptance case fails the broken product |
| LLM output is never evidence | Context remains inert; no AI certification interface |
| Project Policy outranks AI | Mandatory floor and conditional requirements survive profile/advisory selection |
| Mandatory skipped check cannot PASS | Unavailable, filtered, skipped and unexecuted mandatory work blocks clean PASS |
| RunStatus != GateDecision | Separate typed fields; completed dry runs are NOT_EVALUATED, completed regressions FAIL |
| Project isolation enforced | Scoped projects, credentials, run/artifact paths and FTS retrieval; cross-project tests pass |
| Memory requires validation + approval | Reproduction, original fix/regression evidence and explicit review required |
| No automatic merge/deploy | Neither runtime nor workflow implements merge/deployment; feature remains separate from main |
