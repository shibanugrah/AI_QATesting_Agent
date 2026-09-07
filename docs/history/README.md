# Historical / Reference Material

This directory preserves the design history needed for the later QA Engine rebuild while keeping historical executable code out of the active source tree.

Nothing in this directory is current implementation authority.

## Archived PRD

- `PRD2-legacy.md` is the former root `PRD2.md` preserved unchanged for historical context.
- It describes the earlier Codex-assisted/local QA-learning direction and should not be treated as the current product specification.

## Phase-1 reference implementation

The removed `.reference/AI_QATesting_Agent_phase1/` tree remains permanently available in Git history.

Useful reference commits:

- `b309c5bb4dfaa92c567336f06a1793d829495d78` — Phase-1 reference implementation was added.
- `960c608b7a6385a3c2cd720086cbbe6119f88694` — last pre-preparation `main` state containing the `.reference` tree plus saved patch/status artifacts.

To inspect historical files without restoring them into the active tree, use Git, for example:

```bash
git show 960c608b7a6385a3c2cd720086cbbe6119f88694:.reference/AI_QATesting_Agent_phase1/qa_agent/models.py
git show 960c608b7a6385a3c2cd720086cbbe6119f88694:.reference/AI_QATesting_Agent_phase1/qa_agent/planner.py
git show 960c608b7a6385a3c2cd720086cbbe6119f88694:.reference/AI_QATesting_Agent_phase1/qa_agent/security.py
```

### Useful ideas preserved from that experiment

The Phase-1 bundle explored:

- typed test-suite enums;
- URL vs repository target modes;
- `RunRequest` and `TestPlan` concepts;
- included/excluded test reasoning;
- explicit authorization for remote targets;
- early URL-safety checks;
- suite filtering and dry-run/plan concepts;
- strict configuration ideas.

### Why the executable copy was removed from `main`

It duplicated package names such as `qa_agent/`, `executor/`, `tests/`, and `dashboard/` underneath `.reference`, which made it easy for future coding agents to confuse historical code with the active prototype.

It was also still Phase-1-specific: only Smoke/API were intended to execute, repository mode was modeled but not executable, and orchestration remained tied to the older pipeline design.

Use it for lessons, not as code to merge wholesale.

## Saved patch and working-tree snapshot

The root files:

- `ai-qa-before-commit-split.patch`
- `ai-qa-working-tree-status.txt`

were removed from the active tree during repository preparation. They are preserved at commit:

`960c608b7a6385a3c2cd720086cbbe6119f88694`

Example retrieval:

```bash
git show 960c608b7a6385a3c2cd720086cbbe6119f88694:ai-qa-working-tree-status.txt
git show 960c608b7a6385a3c2cd720086cbbe6119f88694:ai-qa-before-commit-split.patch > /tmp/ai-qa-before-commit-split.patch
```

The working-tree snapshot shows an unfinished attempt that touched the active pipeline, runners, reporting, dependencies, and tests while adding config/planner/redaction/security files and URL-safety/selective-orchestration tests.

The saved patch explored stronger ideas including authorization/allowlists, URL/DNS/redirect safety, bounded requests, redaction, and selective orchestration. Those ideas may inform the later rebuild, but the patch must **not** be blindly applied because it belongs to the superseded architecture generation.

## Current authority

For current behavior, start with:

- root `README.md`;
- root `AGENTS.md`;
- active root source packages and tests.

A later QA Engine build specification may replace the active prototype architecture. Until then, historical material cannot override the active tree.
