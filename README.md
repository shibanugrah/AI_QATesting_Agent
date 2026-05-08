# AI QA Testing Agent

Phase-based QA automation scaffold:

- Phase A: generate tests, run API/UI checks, analyze failures, build HTML reports, queue human review, block email until approval.
- Phase B: store failures as local embeddings and retrieve similar past failures during analysis.
- Phase C: queue multiple websites and run jobs in parallel with retry support.

## Run Phase A/B

```powershell
python -m qa_agent.cli run --config examples/example_site.json
```

Output includes a report ID and an HTML report path. The report is also stored in `artifacts/review_queue` with `approval_status: pending`.

## Approve And Send

```powershell
python -m qa_agent.cli approve <REPORT_ID> --notes "Looks good"
python -m qa_agent.cli send-email <REPORT_ID> --to qa@example.com
```

Email is blocked unless the report is approved. The MVP creates an outbox file in `artifacts/outbox`.

## Phase Checkpoints

### Phase A: Core MVP

Run:

```powershell
python -m qa_agent.cli run --config examples/example_site.json
```

Check:

- The command prints `Report ID`, `HTML report`, and `Approval status: pending`.
- `artifacts/reports/<REPORT_ID>.html` exists.
- `artifacts/review_queue/<REPORT_ID>.json` has `approval_status` set to `pending`.
- Sending email before approval fails:

```powershell
python -m qa_agent.cli send-email <REPORT_ID> --to qa@example.com
```

Approve and send:

```powershell
python -m qa_agent.cli approve <REPORT_ID> --notes "Approved by human"
python -m qa_agent.cli send-email <REPORT_ID> --to qa@example.com
```

Check `artifacts/outbox/<REPORT_ID>.eml.txt`.

### Phase B: RAG Learning

Run the same target twice, preferably with one failing route. Check:

- `artifacts/rag/vector_store.json` grows with failure memories.
- The HTML report's Failure Analysis section includes similar past failures.

### Phase C: Scaling

Create multiple config files using `examples/example_site.json` as the template, then run:

```powershell
python -m qa_agent.cli batch --configs examples/example_site.json examples/example_site.json --parallelism 2
```

Check:

- A report is created for each queued target.
- Failed worker jobs are retried according to `max_retries`.

## Real Selenium

The default UI runner uses a simple page-load check so the project works without browser drivers. To enable real Selenium:

```powershell
pip install selenium
$env:QA_AGENT_REAL_SELENIUM="1"
python -m qa_agent.cli run --config examples/example_site.json
```

## Run Batch

```powershell
python -m qa_agent.cli batch --configs examples/example_site.json --parallelism 2
```

## Approval API

```powershell
python -m qa_agent.cli approval-api --port 8088
```

Then approve with:

```powershell
Invoke-WebRequest -Method POST "http://127.0.0.1:8088/approve/<REPORT_ID>?notes=approved"
```

## Run Tests

```powershell
python -m unittest discover -s tests
```

## Streamlit Dashboard

Install dependencies, then run:

```powershell
pip install -r requirements.txt
streamlit run dashboard/streamlit_app.py
```

The dashboard lets you enter a target URL/config, run the existing QA pipeline,
review latest reports, approve or reject reports, send approved reports, and view
AI insights plus pass/fail counts.
