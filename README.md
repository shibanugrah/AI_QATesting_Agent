# QA Engine

QA Engine independently verifies owner-authorized software changes and running applications. Python resolves project policy, executes deterministic checks, seals evidence, and returns a separate run status and release gate. Builder statements and AI text cannot certify results.

This is a local V1 implementation. Controlled acceptance evidence and remaining external validation are recorded in [docs/VERIFICATION.md](docs/VERIFICATION.md).

## Requirements and installation

Python 3.11+ (verified with 3.12), Git, and Node.js 22 for browser checks. Use an isolated environment:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,viewer]"
npm ci --prefix browser_worker
$env:PLAYWRIGHT_SKIP_BROWSER_GC = "1"
npm run install:chromium --prefix browser_worker
npm run typecheck --prefix browser_worker
python -m pytest -q
```

On Linux/macOS, activate with `source .venv/bin/activate`; set `PLAYWRIGHT_SKIP_BROWSER_GC=1`. On Linux install Chromium system dependencies with `npx --prefix browser_worker playwright install --with-deps chromium`. The worker is pinned to Chromium through Playwright Test. Firefox/WebKit are not used.

`pyproject.toml` owns Python dependencies. `requirements.txt` is a compatibility installer. Optional `.[security]` installs pip-audit; the engine remains usable without it. `browser_worker/package-lock.json` locks the separate Node environment. Wheels include the worker sources; for a wheel installation, obtain their path with `python -c "from qa_engine.repository import worker_root; print(worker_root())"` and run `npm ci` there.

## Quick start and owner enrollment

Enrollment authorizes native code execution in that repository. Only enroll code you trust and have permission to test. A native npm script or Pytest plugin can execute project code; this is not an untrusted-code sandbox.

Copy [examples/qa-engine-project.json](examples/qa-engine-project.json), replace its placeholder repository, host, endpoints, selectors, and dedicated staging account. Paths are relative to the config file. Review the allowed command IDs, required checks, hosts, ports, and mutation permission before enrollment.

```text
python -m qa_engine enroll path/to/reviewed-project.json
python -m qa_engine discover my-authorized-project
python -m qa_engine plan my-authorized-project --dry-run
python -m qa_engine run my-authorized-project --dry-run
python -m qa_engine verify-change my-authorized-project --base main
python -m qa_engine run my-authorized-project --profile api
python -m qa_engine verify-fix my-authorized-project --previous-run RUN_ID
python -m qa_engine show my-authorized-project RUN_ID
python -m qa_engine gate my-authorized-project RUN_ID
```

The installed `qa` command is equivalent to `python -m qa_engine`. Place `--data-dir PATH` before the subcommand. The default directory is `.qa-engine/`.

Live planning reads Git but does not run project checks or make target HTTP requests. Dry planning and dry runs execute no subprocess, browser, DNS lookup, or external request. They may read local manifests and write local audit records. A dry run returns `NOT_EVALUATED`, never PASS.

Profiles filter checks in Python before executors. An API profile executes only API checks. A smoke profile executes only endpoints tagged smoke. Mandatory checks filtered out of a run remain blocked and prevent PASS. No profile means available, authorized capabilities plus the mandatory floor. Optional absent scanners are not automatically selected. Advisory additions can expand the set; they cannot remove mandatory checks.

## Policy and capability model

Policy requires at least one check. Unknown fields, implicit type coercions, legacy `api_tests`, and arbitrary command strings are rejected. Use `api_endpoints`.

| Capability | Discovery | Fixed command ID |
|---|---|---|
| Python unit | tests directory / pytest configuration | pytest_unit |
| Python integration/regression | declared Pytest markers | pytest_integration / pytest_regression |
| Ruff | Ruff config | ruff |
| Mypy | Mypy config | mypy |
| Python package build | build-system in pyproject.toml | python_build |
| npm lint/type/build/unit/integration/regression | named package scripts | npm_lint / npm_type / npm_build / npm_unit / npm_integration / npm_regression |
| Dependency scan | requirements.txt plus installed pip-audit | pip_audit |
| API / smoke / security headers | owner endpoint configuration | built-in adapter |
| Browser / accessibility / web diagnostics | journeys plus installed worker | Chromium worker |

An available command must also appear in `allowed_commands`. Conditional glob rules can add mandatory checks for changed files. Without a base comparison, conditional requirements expand conservatively. Change analysis records exact HEAD/base SHA, branch, dirty diff hash, untracked-file content hashes, and changed paths. A requested head that is not checked out is blocked. A changed workspace during execution prevents PASS. Impact analysis is deterministic and conservative; it does not compute a mathematically minimal test set.

API checks support GET, HEAD, OPTIONS, status/text, dotted JSON-value assertions, and expected response headers. Responses, logs, timeouts, requests, and artifacts have limits. HTTP redirects are manually evaluated, every address must satisfy policy, and the connection uses the validated IP with the original TLS hostname. Private/metadata targets are denied. Explicit local policy may allow loopback; it never enables private-network scanning. Browser POST requests additionally require `allow_mutation: true`.

## Browser worker and credentials

Version 1 JSON requests/results bind a journey to a request ID, project, and environment. The TypeScript worker runs Playwright Test with Chromium, configured desktop/mobile viewports, selectors, forms, and explicit assertions. It records screenshots, sanitized traces, console/network failures, and axe violations. Python owns authorization, classification, retries, and gate decisions.

All intercepted browser HTTP is fulfilled through a private per-attempt Python broker using the same destination checks as API requests. Service workers and WebSockets are blocked. Each attempt has a fresh browser context and repeats its dedicated test login. Cookies/auth state are never shared or saved for reuse. There is no storage-state file to copy across projects.

Project config contains credential references mapped to environment-variable names. For example set `QA_STAGING_PASSWORD` privately in your shell/CI, not in JSON or Git. Credentials are passed ephemerally only to their project's worker. Reports/DB/logs/traces are sanitized before retention. Inputs and `[data-qa-private]` elements are masked in screenshots; known secret-bearing DOM text is removed before capture. Trace DOM snapshots, resource bodies, and filmstrip screenshots are deliberately omitted to avoid retaining authentication material.

Automated axe success means no configured automated violations were detected. It does not prove full WCAG compliance.

## Deterministic gate and fix verification

`RunStatus` describes orchestration completion. `GateDecision` is PASS, FAIL, REVIEW_REQUIRED, or NOT_EVALUATED. Check failures produce FAIL; missing or unavailable mandatory work, blocked checks, incomplete state, corrupted evidence, and flaky outcomes cannot produce PASS. Exit codes: 0 PASS (or successful preview/dry-run command), 1 FAIL, 2 REVIEW_REQUIRED, 3 NOT_EVALUATED, 4 invalid input/authorization.

One diagnostic assertion rerun is allowed by default; infrastructure retries are capped at two. Every attempt is retained. FAIL followed by PASS is FLAKY_SUSPECTED and requires review.

`verify-fix` links a confirmed previous failure, reruns the original check, and makes configured regression checks mandatory. Pytest JUnit failures are bound to test IDs and AST body hashes: removed, skipped, or changed original tests cannot validate a fix. API/journey definitions must remain identical. Other native tools are verified at command-check granularity. A builder's statement that it fixed the issue is inert context.

## Evidence, review, and QA Memory

SQLite migration 1 owns projects, repositories, environments, runs, stages, events, checks, attempts, findings, artifacts, incidents, memory records, FTS5, and reviews. Foreign keys, WAL, transactions, and project-qualified queries support concurrent local runs. Each run has 30 durable checkpoints; visual checkpoint 23 is skipped as outside V1. See [architecture](docs/ARCHITECTURE.md).

Artifacts are stored under `projects/<project>/runs/<run>/` with SHA-256, size, redaction, and retention metadata. The database additionally checks the canonical result hash. `gate` rechecks artifact integrity and whether owner policy changed. These hashes detect mutation; they are not remote signatures or protection from an administrator rewriting the entire evidence store.

Local Markdown/HTML reports await human review before export:

```text
python -m qa_engine review-report PROJECT RUN_ID APPROVED --reviewer "Human name"
python -m qa_engine export PROJECT RUN_ID approved-report.md
python -m qa_engine memory-search PROJECT "unit failure"
python -m qa_engine memory-review PROJECT RECORD_ID APPROVED --reviewer "Human name"
```

Report approval permits export and does not override the release gate. There is no email distribution service. Reviews are trusted local operator actions, not an identity/authentication server.

Memory progresses through OBSERVED, REPRODUCED, FIX_VALIDATED, and explicit human APPROVED; REJECTED, STALE, and EXPIRED records are excluded. Trusted retrieval is project-scoped FTS5 and revalidates linked evidence. Changed policy invalidates old trust. Fingerprints are versioned deterministic similarity keys, not proof of a common root cause. No embeddings, vector DB, semantic RAG, or AI generation are used.

## Python API and viewer

```python
from qa_engine import Engine, RunRequest

engine = Engine(".qa-engine")
plan = engine.plan(RunRequest(project_id="enrolled-project", dry_run=True))
result = engine.verify_change("enrolled-project", base_ref="main")
print(result.run_status, result.gate.decision, result.gate.reason_codes)
```

Other stable operations are `run`, `verify_fix`, `get_run`, `gate`, `find_incidents`, `review_memory`, and report review/export. `investigate` executes configured verification with inert contextual notes. AI-assisted investigation is not implemented.

`python -m streamlit run dashboard/streamlit_app.py` opens a thin local viewer/controller over the same API.

## GitHub and validation

[The workflow](.github/workflows/qa-engine.yml) runs on owner main pushes or explicit dispatch. Default permissions are contents/read and pull-requests/read, with no persisted checkout credentials. It runs tests, the acceptance harness, and a self-project gate, then uploads machine evidence and writes a job summary. Arbitrary pull request code is not automatically trusted. Optional `--github-event EVENT_JSON --base BASE_SHA` binds PR metadata only when it matches actual base/HEAD. GitHub green/skipped status cannot override the engine gate. PR posting and merges are not implemented.

```text
python -m pytest -q --cov=qa_engine --junitxml=artifacts/engine-tests.xml
python -m qa_engine.acceptance --output artifacts/acceptance
python tools/verify_clean_install.py
python -m tools.verify_live_scanner
npm run typecheck --prefix browser_worker
```

The last scanner command requires `.[security]` and checks a controlled vulnerable requirement without installing it. The acceptance harness preserves fixture repositories, databases, screenshots, traces, JUnit, logs, and a 30-scenario table. `validate_pilots(engine, explicit_enrolled_ids)` supports later owner-authorized pilots. Controlled fixtures are not external commercial validation.

## Migration and remaining boundaries

The older `agents/`, `executor/`, `rag/`, scheduler, email, and report packages are retained as historical prototype source; they are not included in the installed engine. The old CLI forwards to the new CLI. `QAPipeline` is disabled so it cannot bypass enrollment. Historical tests remain compatibility checks, not V1 acceptance evidence. The untracked nested snapshot is untouched.

No production tests, untrusted repository sandbox, automatic repair/merge/deployment, visual regression, Firefox/WebKit, performance/SEO, hosted service, vector memory, or external messaging are provided. Browser evidence deliberately omits trace bodies/DOM snapshots; screenshots require the owner to mark application-specific private areas. External three-project pilots and hosted GitHub Actions execution require separate verification. Retention deadlines are recorded and memory expiry is enforced; automated deletion of artifact files is not implemented. Runs interrupted by abrupt process termination remain RUNNING/NOT_EVALUATED and must be rerun, not resumed automatically.

The prepared history/archive map remains in [docs/history/README.md](docs/history/README.md). The removed reference tree and root patch/status files are available through Git history only.
