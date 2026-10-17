# Data Ingestion and SQL Connectors

## 1. Canonical interface

All sources must converge on the same logical interface:

```text
preview(source) -> columns + inferred types + limited rows + mapping suggestions
read(source, table/sheet, row_limit) -> tabular data + source metadata
normalize(data, mapping) -> canonical transactions + row-level validation results
analyze(canonical transactions, options) -> metrics + data quality + alerts
```

The UI and API must distinguish:
- original source data
- canonical mapped fields
- values that parsed successfully
- rows excluded from rule calculations
- alert evidence references back to source row numbers

## 2. CSV and Excel import

Supported formats: `.csv`, `.xlsx`, and optionally legacy `.xls` when the parser dependency is enabled. Initial implementation should use conservative limits, configurable by the backend:
- maximum upload size: 20 MiB
- maximum analyzed rows: 200,000 (lower this for constrained environments)
- preview rows: 20
- SQL preview/import cap: 5,000 rows per request

Validate the extension, detected file signature/format, file size, and parse success. Do not trust the browser-provided MIME type. Reject empty files, empty headers, duplicate column names (or disambiguate them safely), unsupported workbook formats, and malformed files with a useful message.

For workbooks, allow sheet selection and display the sheet's column profile before analysis. Never execute spreadsheet formulas. Treat cell contents as values; escape formula-leading characters when exporting CSV to prevent spreadsheet formula injection.

Column mapping should suggest matches (case-insensitive normalized header names) for:
- timestamp/date/time
- amount/transaction amount/value
- source/from/debit/origin account
- destination/to/credit/beneficiary account
- transaction/reference/id
- customer/client
- currency/ccy
- type/channel/status

Mapping suggestions are not confirmations. The analyst reviews the mapping before analysis.

## 3. Data normalization and quality

- Parse timestamps with explicit handling of invalid and ambiguous values; preserve the original display value for evidence.
- Keep account and transaction identifiers as strings, preserving leading zeros.
- Parse monetary amounts as numeric values and report failures. Do not silently convert arbitrary text to zero.
- Do not sum mixed currencies into one misleading total.
- Identify duplicate transaction IDs, missing required values, invalid timestamps, invalid amounts, unsupported signs and likely duplicate rows.
- Report exclusion counts and examples. Never silently discard suspiciously malformed data.

## 4. SQL connection UX

1. User selects database engine.
2. User enters host, port, database, username and password (or a connection URL) in the local portal.
3. API validates driver and host policy, connects with a timeout, and tests permissions.
4. API lists accessible schemas/tables using database metadata inspection.
5. User selects a table and sees a bounded preview and column list.
6. User maps columns and runs analysis with a row cap.
7. The UI clears secret inputs when leaving the connection workflow; API discards credentials after each request.

The production design should use a dedicated read-only database user and an administrator-configured network allowlist. Prefer separately entered connection fields over logging or exposing a full connection URL containing credentials.

## 5. Supported engine policy

Initial targets:
- PostgreSQL (SQLAlchemy + psycopg driver)
- MySQL/MariaDB (SQLAlchemy + PyMySQL driver)
- SQLite only for local development and only inside a dedicated approved directory

Reject unknown dialects, unexpected driver names, remote SQLite URLs, local file paths outside the configured source-data directory, and hosts not allowed by deployment policy. In production, explicit host allowlisting and network-level egress restrictions are mandatory. Do not rely on frontend validation.

## 6. Query design

The browser must never submit raw SQL. For listing and preview:
- use SQLAlchemy inspection/reflection;
- validate schema/table identifiers against the discovered catalogue;
- quote identifiers using the active dialect's identifier preparer;
- add a hard row limit;
- set connection and statement timeouts where supported;
- disallow DDL/DML by connecting with read-only privileges;
- do not perform writes to the source database;
- do not persist a credential-bearing URL in logs, audit payloads, error messages or client storage.

A row limit alone is not sufficient for performance safety; add a configurable query timeout and prefer indexed timestamp filters for future large-table analysis.

## 7. Future ingestion work

- asynchronous/background imports for large data
- incremental imports using a trusted watermark
- source-to-canonical mapping templates per institution
- schema drift alerts
- checksum and duplicate-import detection
- approved object storage and retention controls for queued workloads
- database-specific read-only transaction enforcement
- institution-managed secrets rather than user-supplied passwords for recurring schedules
