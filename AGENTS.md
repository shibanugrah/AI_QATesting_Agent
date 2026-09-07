# Repository Instructions — QA Engine Preparation Baseline

## Current purpose

This repository is the **authoritative legacy/prototype baseline** for a later QA Engine rebuild.

The future product is:

> QA Engine is an independent software verification layer for humans and AI agents that converts software changes and running applications into reproducible evidence and deterministic quality decisions.

Core invariant:

> Builder ≠ Verifier.

## Source-of-truth rules

1. Treat the active root source tree as implementation authority.
2. Treat `docs/history/` as historical/reference material only.
3. Historical commits, old PRDs, saved patches, and prior Phase-1 code may provide ideas, but they do not override the current approved architecture.
4. Inspect actual code before claiming a capability works.
5. Never describe a roadmap or modeled capability as implemented unless it has been verified in the active baseline.

## Locked architecture principles for the later rebuild

These are constraints for a future approved build, not instructions to implement them now:

- deterministic-first verification;
- LLM output is never evidence;
- owner project policy outranks AI planning;
- all policy-mandatory checks must execute successfully before a release gate can return PASS;
- the 30 checkpoints are an observable execution contract, not a rigid internal architecture;
- internal orchestration may use a DAG/state machine;
- repository-native capabilities must be discovered rather than forcing the same checklist on every project;
- Python core;
- small TypeScript Playwright Test worker for browser execution;
- Chromium only in initial V1;
- SQLite + FTS5 before vector retrieval;
- GitHub first-class, read-only by default;
- project, credential, memory, and baseline isolation are mandatory.

## Current baseline validation

For the current prototype, use:

```bash
python -m unittest discover -s tests
```

If the environment cannot execute a check, report it as `NOT REVERIFIED` rather than claiming success.

## Safety

- Do not run destructive commands.
- Do not rewrite Git history or force-push.
- Do not introduce or expose secrets.
- Do not test systems without ownership or explicit authorization.
- Do not add arbitrary-shell execution from untrusted input.
- Do not make production mutations.

## Important non-goal

Do **not** start the future QA Engine implementation unless a separate, explicit implementation specification has been provided.
