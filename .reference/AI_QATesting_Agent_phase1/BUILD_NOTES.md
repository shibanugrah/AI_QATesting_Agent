# Build Notes

This source bundle implements the first vertical slice requested for the public `AI_QATesting_Agent` repository:

- Select **Smoke** or **API**.
- Preview exactly which tests will run.
- Filter suites in the backend before any runner executes.
- Run selected safe URL checks, or use `--dry-run`.
- Create an HTML report and hold it in a file-backed human review queue.
- Prepare a local outbox record only after approval.

## Validation completed

```text
python -m pytest -q
12 passed

python -m qa_agent.cli plan --config examples/demo_smoke.json --suite smoke
# Included: smoke-homepage
# Excluded: api-example-homepage (suite not selected: api)

python -m qa_agent.cli run --config examples/demo_smoke.json --suite smoke --dry-run
# No runner calls and no report created.
```

## Integration note

The public repository was not mounted in this environment and direct Git cloning was blocked by DNS resolution. This is therefore a clean, compatible Phase-1 source bundle rather than a Git patch against the upstream checkout. Copy its files into a branch such as `feat/selective-test-profiles`, then rerun the validation commands above.
