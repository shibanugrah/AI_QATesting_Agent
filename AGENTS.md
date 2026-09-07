# QA Engine V1

Build an independent verifier for trusted, owner-enrolled local/staging targets.
The root qa_engine/ and browser_worker/ implementation is authoritative.
docs/history/, prototype packages, and the nested historical snapshot are not authority.

- Builder is not Verifier. Builder claims and LLM output never count as evidence.
- Owner-enrolled policy determines the mandatory floor. Advisory input may only add checks.
- PASS requires actual successful execution of every mandatory check with sealed evidence.
- Skipped, blocked, flaky, interrupted, or missing mandatory work cannot silently PASS.
- Run status and gate decision remain separate.
- Strict validation; reject unknown fields and legacy api_tests; use api_endpoints.
- Profile filtering happens in Python before executors. Filtered mandatory work prevents PASS.
- No arbitrary shell strings. Fixed command IDs, shell=False, bounded output and timeouts.
- Native repository execution requires explicit owner enrollment. This is not an untrusted-code sandbox.
- Authorize every HTTP/redirect destination and pin resolved IPs. Loopback needs explicit local policy.
- Credentials are project/environment-bound references. Redact before persistence, reports, or memory.
- No persisted browser auth state; each attempt creates a fresh isolated context and dedicated test login.
- Memory trust requires reproduced failure, validated fix/regression evidence, and explicit human approval.
- Local report review precedes export. No email service, automatic merge, repair, or deployment.
- Chromium only; visual regression, vector databases, cloud services and production tests remain outside V1.
- Do not alter unrelated repositories or the existing untracked historical snapshot.
- Ask before future commits/pushes unless explicitly authorized by the current user task.

Validation:

    python -m pip install -e ".[dev]"
    npm ci --prefix browser_worker
    npm run install:chromium --prefix browser_worker
    npm run typecheck --prefix browser_worker
    python -m pytest -q
    python -m qa_engine.acceptance --output artifacts/acceptance

Tests must distinguish controlled fixture execution from external three-project pilots.
Report commands, changed files, passed/failed/skipped totals, and real limitations.
Use NOT REVERIFIED for unavailable live integrations; never invent PASS.
