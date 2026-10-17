# API Contract — Initial Ingestion MVP

Base path: `/api`. Payload schemas below describe the intended API; concrete endpoints may evolve as implementation lands.

## Health

### `GET /api/health`
Returns service availability and API version. Must not expose environment variables or secrets.

## File preview

### `POST /api/files/preview`
Content type: `multipart/form-data`

Fields:
- `file`: CSV or Excel file.
- `sheet_name`: optional workbook sheet name; if omitted, use the first sheet or require a choice for multi-sheet workbooks.

Returns:
- `filename` (sanitized display name)
- `row_count` (bounded count or indication of truncation)
- `columns[]`: name, inferred type, null count, sample values
- `preview_rows[]`: bounded values
- `mapping_suggestions`: canonical field to proposed source column
- `warnings[]`

## File analysis

### `POST /api/files/analyze`
Content type: `multipart/form-data`

Fields:
- `file`
- `mapping`: JSON object mapping canonical fields to source column names.
- `options`: JSON object of explicitly configurable thresholds.
- `sheet_name`: optional.

Required mapping keys: `timestamp`, `amount`, `source_account`.

Response:
- `summary`: transaction count, analyzed count, excluded count, date range, distinct-account counts.
- `totals_by_currency[]`: totals and averages grouped by currency or a source-default bucket.
- `data_quality[]`: finding key, severity, message, affected count, source row examples.
- `alerts[]`: alert ID, rule ID/version, severity, title, explanation, evidence row references and measured values.
- `rule_counts`: alert counts grouped by rule/severity.
- `warnings[]`: limitations such as a missing optional field or mixed currencies.

## SQL connector (request-scoped credentials)

### `POST /api/sql/test`
JSON body: `{ "connection": { ...connection fields... } }`
Returns successful connection and engine label only; must never return the password or credential-bearing URL.

### `POST /api/sql/tables`
JSON body: connection fields.
Returns discovered schemas/tables from the approved source. It must not execute user-submitted SQL.

### `POST /api/sql/preview`
JSON body: connection fields, validated schema/table, bounded `limit`.
Returns columns, inferred types, preview rows, mapping suggestions and count/truncation metadata.

### `POST /api/sql/analyze`
JSON body: connection fields, validated schema/table, canonical mapping, rule options and bounded row limit.
Uses the same analysis engine as file ingestion.

## Canonical mapping

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

Only `timestamp`, `amount`, and `source_account` are mandatory for the initial analysis. The user confirms suggestions.

## Example analysis options

```json
{
  "large_amount_threshold": 1000000,
  "velocity_count_threshold": 10,
  "velocity_window_minutes": 60,
  "structuring_reference_threshold": 1000000,
  "structuring_min_transactions": 3,
  "structuring_window_hours": 24,
  "outlier_mad_multiplier": 6
}
```

These are illustrative demonstration values, not legal or regulatory thresholds.

## Error model

Use standard HTTP status codes and a safe response body, e.g.:

```json
{
  "error": {
    "code": "INVALID_MAPPING",
    "message": "Map a timestamp, amount, and source account column before analysis.",
    "details": ["source_account mapping is missing"]
  }
}
```

Never put passwords, full connection URLs, access tokens, or unredacted financial rows in error details. Do not expose Python tracebacks to the browser.
