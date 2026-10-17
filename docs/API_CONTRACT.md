# API Contract — SentinelAML Prototype

Base path: `/api`. Protected routes require:

```http
Authorization: Bearer <short-lived access token>
```

The access token lasts one hour and is held in frontend memory. Reloading the web page requires signing in again. The local admin bootstrap account is configured with `SENTINELAML_ADMIN_EMAIL` and `SENTINELAML_ADMIN_PASSWORD`.

## Health and authentication

- `GET /api/health` — public liveness check; returns service and version.
- `POST /api/auth/login` — public. JSON body: `{ "email": "...", "password": "..." }`. Returns `access_token`, `token_type`, expiry and minimal user profile.
- `GET /api/auth/me` — returns the authenticated user's profile.
- `GET /api/overview` — the current user's latest analysis summary, case counts and policy-document count.

## File ingestion and analysis

- `POST /api/files/preview` — authenticated multipart upload of CSV/XLSX/XLS with optional `sheet_name`. Returns bounded preview rows, inferred column types, mapping suggestions and warnings.
- `POST /api/files/analyze` — authenticated multipart upload with `file`, JSON string `mapping`, JSON string `options` and optional `sheet_name`. Uses the common analysis engine, persists analysis summary/alerts, and returns `analysis_run_id`.

Required canonical mappings: `timestamp`, `amount`, `source_account`.

Example mapping:
```json
{
  "transaction_id": "Transaction Reference",
  "timestamp": "Posting Date",
  "amount": "Transaction Amount",
  "source_account": "Debit Account",
  "destination_account": "Credit Account",
  "customer_id": "Customer Number",
  "currency": "Currency"
}
```

## SQL source connector

All routes below are authenticated. Connection credentials are request-scoped and must not be stored by the client.

- `POST /api/sql/test` — test connection.
- `POST /api/sql/tables` — list accessible schema/table metadata.
- `POST /api/sql/preview` — bounded preview of a discovered table.
- `POST /api/sql/analyze` — bounded table read + the common analysis engine; returns `analysis_run_id`.

Supported engines are PostgreSQL, MySQL/MariaDB, and SQLite files under `SENTINELAML_SQLITE_ROOT`. Remote database hosts must be explicitly allowlisted at the API server. The browser cannot submit raw SQL.

## Persistent cases

- `GET /api/cases?limit=100` — list cases the authenticated user may access.
- `POST /api/cases` — create a case from a persisted run and an alert:
```json
{
  "analysis_run_id": "run-id-from-analysis",
  "alert_id": "alert-id-from-that-run",
  "title": "Optional analyst title",
  "analyst_notes": "Optional initial notes"
}
```
- `GET /api/cases/{case_id}` — case snapshot plus event history.
- `PATCH /api/cases/{case_id}` — update status, disposition, notes, or assignment according to the current role guardrails.
- `POST /api/cases/{case_id}/investigate` — JSON body `{ "question": "optional analyst question" }`. Runs the bounded four-agent workflow and persists a draft report for human review.

Supported statuses: `open`, `in_review`, `escalated`, `closed`.

Supported dispositions: `pending`, `no_concern_identified`, `escalated_for_review`, `reporting_consideration`, `insufficient_information`.

## Policy intelligence

- `GET /api/policies` — list indexed policy documents.
- `POST /api/policies/upload` — compliance role only; multipart `file` and optional `title`. Accepts PDF, TXT and Markdown. Extracted text chunks persist in the metadata database.
- `POST /api/policies/search` — JSON body `{ "query": "suspicious transaction monitoring", "limit": 5 }`. Returns source-linked lexical matches.

The current retrieval approach is lexical term overlap, not semantic embeddings. Scanned PDFs without extractable text are rejected; OCR is not built into the MVP.

## Audit activity

- `GET /api/audit?limit=100` — compliance/admin/auditor role only. Returns DB-backed application events.
- Events include authentication, analysis run, policy upload, case creation/update, and investigation-report generation.
- The current audit table is not tamper-evident and is not a certified compliance archive.

## Investigation workflow and model provider

The workflow runs four bounded components: planner, evidence analyst, policy retrieval, and report synthesis. It uses saved alert snapshots, analysis summaries, and retrieved policy chunks; raw uploaded transaction rows are not persisted.

External LLM synthesis is disabled by default. Set `SENTINELAML_LLM_PROVIDER=openai`, `OPENAI_API_KEY`, and an approved `SENTINELAML_LLM_MODEL` only after institution security/legal approval. The integration sends a minimized alert summary and retrieved policy passages; it must not be enabled for regulated customer data without explicit approval. If external synthesis fails or its citations do not match retrieved chunks, the workflow falls back to a deterministic evidence report.

## Example analysis options

```json
{
  "large_amount_threshold": 1000000,
  "velocity_count_threshold": 10,
  "velocity_window_minutes": 60,
  "structuring_reference_threshold": 1000000,
  "structuring_min_transactions": 3,
  "structuring_window_hours": 24,
  "outlier_mad_multiplier": 6,
  "outlier_min_transactions": 8
}
```

Thresholds are demonstration heuristics, not legally mandated values.

## Error model

Validation and application errors use standard HTTP status codes. The safe error envelope may be:
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "The request contains invalid fields.",
    "details": [{"field": "mapping", "message": "Invalid value"}]
  }
}
```
Some FastAPI domain errors use `detail`. Never expose passwords, full connection URLs, access tokens, unredacted financial data, or Python tracebacks in client-visible error messages.
