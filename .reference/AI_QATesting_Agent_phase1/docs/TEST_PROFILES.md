# Test Profiles

## Smoke

Fast release-confidence checks. In this release these can be page availability checks or explicitly configured API checks tagged `smoke`.

## API

Safe GET/HEAD HTTP checks that assert the configured response status and optional text.

## Planned profiles

`unit`, `integration`, `e2e`, `regression`, `accessibility`, `visual`, and `security_baseline` exist in the domain model to keep configuration stable. They fail clearly if selected because their execution adapters are not implemented yet.

## Backend contract

Suite filtering happens before any request or report creation. Selecting `--suite smoke` executes only cases whose `suite` equals `smoke`.
