# Product Scope — Selective Test Profiles (First Release)

## Product statement

Build a **local QA orchestration tool** that lets an authorized user choose a supported test profile, preview exactly which tests will run, execute only the selected tests, review generated artifacts, and approve the final report before delivery.

The first release must be demonstrable end to end through both the CLI and Streamlit dashboard.

## First-release goal

The primary workflow is:

```text
Select Smoke or API
        ↓
Preview included and excluded tests
        ↓
Run only the selected suite
        ↓
Capture results and artifacts
        ↓
Generate a reviewable report
        ↓
Require human approval before delivery
```

## Target users

- Developers validating a local, demo, or staging application before release.
- QA engineers who need a lightweight way to selectively run critical checks.
- Solo builders who want clear evidence of what ran and why.

## Supported target modes

### Website or staging URL

Supported in the first release for:

- Smoke checks
- API checks

A user must explicitly confirm that they own, operate, or are authorized to test the target.

### Local repository

Defined in the domain model, but repository execution is not part of the first-release implementation. It will later support unit and integration suites through approved test adapters rather than arbitrary commands.

## Supported test profiles in the first release

### Smoke

Fast, critical-path checks that provide release confidence. Initial examples:

- API health endpoint returns the expected status.
- Homepage responds successfully.
- Login route or other essential route renders expected content.

### API

Configured, safe API checks using approved methods and assertions. Initial examples:

- Expected HTTP status code.
- Required response text.
- Basic endpoint availability.

## Planned but not implemented in the first release

These profiles may exist as explicit roadmap items or disabled UI options, but must not be presented as working functionality until implemented:

- Unit
- Integration
- End-to-end browser workflows
- Regression
- Accessibility
- Visual regression
- Security baseline

## Explicitly out of scope for the first release

- LLM-generated tests or autonomous test planning.
- Semantic RAG or vector-database retrieval.
- Autonomous code fixes.
- Cloud deployment or multi-user tenancy.
- CI/CD execution with personal Codex credentials.
- Public scanning, offensive security testing, or destructive HTTP actions.
- Redis, Celery, distributed workers, or production queue infrastructure.
- Arbitrary shell commands supplied through user configuration.

## Functional requirements

1. A test case has a suite or profile field.
2. A run request contains selected suites, target mode, environment, fail-fast setting, and dry-run setting.
3. Backend filtering happens before execution.
4. When `selected_suites=["smoke"]`, only smoke-tagged tests execute.
5. The plan shows included tests, excluded tests, and exclusion reasons.
6. Dry-run produces a plan without making HTTP requests or running browser actions.
7. Reports record selected suites, executed test IDs, outcomes, and artifact paths.
8. Existing human approval remains required before report delivery.
9. Invalid configuration fields fail with clear validation errors.
10. URL targets are restricted to authorized, safe destinations.

## Safety boundaries

The first release must:

- Require authorized-target confirmation.
- Restrict execution to configured and allowed targets.
- Block localhost, private, link-local, metadata-service, and internal-network destinations.
- Default to safe HTTP methods such as `GET` and `HEAD`.
- Limit redirects, response size, request count, and run duration.
- Store secrets outside configuration files.
- Keep an execution record for every run.

## Acceptance criteria

The first release is complete only when all of the following are true:

- A user can select **Smoke** from the CLI and Streamlit dashboard.
- The preview clearly shows included and excluded tests.
- The backend guarantees that only selected-suite tests execute.
- Selecting Unit for a URL target fails with a clear message.
- Invalid configuration fails loudly instead of being silently ignored.
- Dry-run creates a plan without executing tests.
- Reports include selected suites and executed test IDs.
- A controlled failure produces a useful artifact.
- Human approval still gates report delivery.
- The repository test suite passes with Pytest.

## Success metric for this milestone

A reviewer can watch a short demonstration and understand, without reading source code, that selecting **Smoke** runs only the intended critical checks and that report delivery remains human-controlled.

## Honest positioning

Until later phases are implemented, describe the project as:

> A local QA orchestration prototype for selective smoke and API checks with reviewable reports and human approval before delivery.

Do not claim LLM-generated tests, semantic RAG, full end-to-end coverage, production readiness, CI/CD automation, or real email delivery unless those features are directly implemented and demonstrated.
