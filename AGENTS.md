# AI QA Testing Agent

## Project goal
Build a local QA orchestration tool for authorized targets.

## Current Phase 1 goal
Implement selectable Smoke and API test profiles only.

## Required behavior
- Selecting smoke must execute only smoke-tagged tests.
- Selecting api must execute only api-tagged tests.
- Filtering must happen in backend code before any runner executes.
- Support preview and dry-run behavior.
- Preserve the existing human approval gate before report delivery.
- Use strict configuration validation.
- Reject legacy `api_tests`; use `api_endpoints`.
- Do not allow arbitrary shell commands from user configuration.
- Use only safe URL checks by default.

## Scope limits
- Do not claim LLM generation, RAG, semantic search, production deployment, real email delivery, or full E2E support unless actually implemented.
- Do not add Playwright, CI/CD, vector databases, Redis, Celery, or cloud deployment in this Phase 1 task.
- Do not commit, push, delete files, or alter Git history without asking.

## Validation
Run pytest and provide:
1. changed files
2. tests passed/failed
3. commands used
4. remaining limitations