# QA Engine V1 architecture and decisions

## Authority and boundaries

`qa_engine` is the installed Python product. It depends only on Pydantic for strict typed contracts; optional executors have explicit capability/readiness checks. The Node package owns browser execution only. Prototype modules are excluded from the wheel and their orchestrator is disabled. Historical snapshots and PRD2 are not implementation authority.

The runtime is for owner-enrolled repositories and local/staging targets. Enrollment is a trusted local administrative action. Native tests, plugins, build backends, and npm scripts execute repository code. V1 does not sandbox a malicious repository or protect evidence against an administrator rewriting both the database and every hash. AI and caller context have no gate-authority interface.

Windows subprocesses are attached to a kill-on-close Job Object; normal child processes cannot outlive the executor handle. Unix processes use isolated process groups for timeout cleanup. This bounds ordinary trusted tool trees, not arbitrary adversarial OS activity.

## Orchestration decision

The engine uses a durable transition state machine and capability-group execution, with dependency barriers between intake, planning, authorization/readiness, checks, evidence validation, classification/fix verification, gate, and report. There are not thirty independent business-logic functions. A stage can represent several plan items; separate native suites and browser viewport executions retain individual attempts.

Execution is sequential within one run to avoid concurrent commands racing on a mutable owner checkout. Separate projects/runs can execute concurrently using independent connections, run namespaces, and SQLite WAL. This favors reproducible workspace evidence over parallelizing tools that may write build outputs. Before/after repository snapshots detect changed execution inputs. Local resume is intentionally replaced by explicit rerun; abrupt interruption preserves nonterminal/non-PASS state.

| # | Observable checkpoint | Actual responsibility |
|---|---|---|
| 1 | Run intake | Persist initial run identity |
| 2 | Project / target / environment resolution | Load enrolled context |
| 3 | Authorization & permission evaluation | Require enrollment and policy identity |
| 4 | Credential capability binding | Resolve selected project secret references; dry-run skipped |
| 5 | Target safety validation | Validate selected URL destinations; per-request checks repeat at execution |
| 6 | Repository/environment snapshot | Exact checked-out Git SHA/workspace; absent/dry repository skipped |
| 7 | Requirement/context ingestion | Accept bounded inert caller text |
| 8 | Change/diff analysis | Base/head and dirty changed paths |
| 9 | Risk classification | Deterministic path/config hints; UNKNOWN without comparison |
| 10 | Prior trusted-context retrieval | Approved, unexpired, evidence-valid project FTS5 records |
| 11 | Test/capability inventory discovery | Manifests, markers, installed adapter readiness |
| 12 | Impact mapping | Conditional owner glob rules; conservative expansion |
| 13 | Test-plan generation | Typed versioned items and mandatory floor |
| 14 | Plan policy validation | Profiles/command allowlist; filtered mandatory checks remain represented |
| 15 | Execution workspace & tool readiness | Confirm current policy hash; discovered adapters |
| 16 | Static/lint execution | Ruff or approved npm lint |
| 17 | Build/type/package verification | Python build, Mypy, approved npm build/type |
| 18 | Unit execution | Pytest unit or npm test |
| 19 | Integration execution | Integration and regression native suites |
| 20 | API/contract execution | Safe structured endpoint assertions |
| 21 | Browser smoke/E2E execution | Smoke-tagged HTTP checks and Chromium journeys |
| 22 | Accessibility execution | Live axe in Chromium |
| 23 | Visual execution | SKIPPED: CAPABILITY_NOT_IN_V1_POLICY |
| 24 | Web diagnostics | Journey-associated console/network evidence and assertions |
| 25 | Defensive security baseline | Security headers and optional/required pip-audit |
| 26 | Evidence sealing & failure normalization | Artifact hashes and post-run workspace comparison |
| 27 | Reproduction & flaky/environment discrimination | Retained attempts and deterministic findings |
| 28 | Fix verification & relevant regression | Original check/test identity plus regression floor |
| 29 | Gate decision + learning/audit update | Deterministic decision and untrusted memory observations |
| 30 | Final evidence report | Markdown/HTML, canonical JSON, manifest |

Stages record version, timestamps, status, executor/version, input/output/evidence refs, budget/retry fields, reason codes and policy version. Only relevant fields are populated; skipped stages are not represented as execution success. A report is local evidence pending review; human export approval is an independent review record and cannot modify gate results.

## HTTP and browser transport decision

Python's standard HTTP parser operates over a socket connected directly to the validated IP. HTTPS keeps the original server name for certificate validation. No environment proxy or automatic redirect can bypass URLGuard. Each DNS answer must be globally routable except an explicitly authorized local loopback fixture. Methods, ports, hosts, query secrets, total request counts, response size and deadlines are bounded.

The browser's route handler does not independently decide host authorization. A per-attempt loopback broker with an ephemeral random token forwards HTTP to the Python client. Context-wide interception covers frames/popups. Service workers and WebSockets are blocked; unrestricted browser network protocols are not a supported V1 journey feature. Browser contexts are disposable and credentials never become storage-state artifacts.

The JSON protocol checks schema version, project/environment/request IDs, journey identity, complete viewport coverage, Playwright status, and evidence paths. Python owns retries and classification. Worker startup/protocol failures cannot become successful journey execution. No final gate, memory, GitHub, or AI logic lives in Node.

## Evidence and secret handling decision

Evidence is capped per file and per run and namespaced by project/run. Pytest generates JUnit outside the target checkout; retained JUnit is sanitized. Screenshots mask inputs and owner-marked private areas. Traces retain action/timing metadata, with DOM snapshots, resource payloads, cookies/auth headers and screenshots omitted. Name/value header representations are explicitly sanitized. Raw worker scratch files are temporary; they never enter the normal retained manifest.

The canonical result and manifest are sealed separately in the artifacts table to avoid self-referential hashes. Gate/review/retrieval verify all registered artifact hashes. The canonical initial result stays immutable; later human reviews are separate database events. Artifact deadlines are metadata, and memory expiration is enforced; disk deletion is not automated.

Unknown private content painted into canvases/images cannot be reliably identified by text redaction. Owners must mark application-specific private regions with `data-qa-private`; do not test production customer sessions. These are controlled test-account browser artifacts, not a general content de-identification system.

## Persistence and memory decision

Migration 1 is owned by `qa_engine/migrations/001_initial.sql`. SQLite foreign keys tie project/run entities together; FTS5 is joined back to relational project/state/expiry/policy filters. Gate evidence resides in run/check/attempt/artifact records, not free-text memory.

Memory records begin OBSERVED or REPRODUCED after actual stable failing attempts. Fix verification plus required regression can produce FIX_VALIDATED. Human review is the only path to APPROVED. Retrieval rechecks original/fix evidence integrity and excludes unapproved, stale, rejected, expired, or policy-incompatible knowledge. Re-enrollment with changed project configuration invalidates prior approval.

Pytest fixes bind original failing JUnit test IDs and test-function AST hashes. Removing or weakening the original test cannot validate a fix. API and journey definitions must match prior evidence. Other native adapters bind at check-command granularity; arbitrary ecosystem test-case introspection is not implemented.

## Official references consulted

- [Playwright Test configuration](https://playwright.dev/docs/test-configuration) and [project configuration](https://playwright.dev/docs/test-projects)
- [Playwright route API](https://playwright.dev/docs/api/class-route) and [tracing API](https://playwright.dev/docs/api/class-tracing)
- [Playwright automated accessibility with axe](https://playwright.dev/docs/accessibility-testing)
- [Pydantic strict validation](https://docs.pydantic.dev/latest/concepts/strict_mode/)
- [Python HTTP client](https://docs.python.org/3/library/http.client.html)
- [SQLite FTS5](https://www.sqlite.org/fts5.html), [foreign keys](https://www.sqlite.org/foreignkeys.html), and [WAL](https://www.sqlite.org/wal.html)
- [Git diff](https://git-scm.com/docs/git-diff)
- [GitHub Actions workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)
- [pip-audit](https://pypa.github.io/pip-audit/)
- [Windows Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)
- [Streamlit AppTest](https://docs.streamlit.io/develop/api-reference/app-testing)
