"""Bounded file ingestion and schema inference for SentinelAML."""
from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import HTTPException, UploadFile

DEFAULT_MAX_UPLOAD_MB = 20
DEFAULT_MAX_ROWS = 200_000
PREVIEW_ROWS = 20
ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}

ALIASES: dict[str, tuple[str, ...]] = {
    "transaction_id": ("transaction id", "transaction_id", "txn id", "txn_id", "reference", "transaction reference", "ref no", "transaction no"),
    "timestamp": ("timestamp", "transaction date", "date", "date time", "datetime", "posting date", "created at", "txn date", "value date"),
    "amount": ("amount", "transaction amount", "txn amount", "value", "transaction value", "debit amount", "credit amount"),
    "source_account": ("source account", "source_account", "from account", "from_account", "debit account", "origin account", "account number", "account no", "sender account"),
    "destination_account": ("destination account", "destination_account", "to account", "to_account", "credit account", "beneficiary account", "recipient account"),
    "customer_id": ("customer id", "customer_id", "customer number", "client id", "cif", "party id"),
    "currency": ("currency", "ccy", "currency code"),
    "transaction_type": ("transaction type", "txn type", "type", "product"),
    "channel": ("channel", "transaction channel", "source channel"),
    "status": ("status", "transaction status", "txn status"),
    "country": ("country", "country code"),
    "balance_after": ("balance after", "balance_after", "closing balance", "available balance"),
}


def max_upload_bytes() -> int:
    try:
        return max(1, int(os.getenv("SENTINELAML_MAX_UPLOAD_MB", str(DEFAULT_MAX_UPLOAD_MB)))) * 1024 * 1024
    except ValueError:
        return DEFAULT_MAX_UPLOAD_MB * 1024 * 1024


def max_analysis_rows() -> int:
    try:
        return max(1, int(os.getenv("SENTINELAML_MAX_ANALYSIS_ROWS", str(DEFAULT_MAX_ROWS))))
    except ValueError:
        return DEFAULT_MAX_ROWS


def _clean_display_filename(filename: str | None) -> str:
    # Display only; never use the supplied filename as a filesystem path.
    return Path(filename or "uploaded-data").name[:160]


async def read_upload(file: UploadFile, sheet_name: str | None = None) -> tuple[pd.DataFrame, dict[str, Any]]:
    filename = _clean_display_filename(file.filename)
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Unsupported file type. Upload CSV, XLSX, or XLS.")
    raw = await file.read(max_upload_bytes() + 1)
    if not raw:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    if len(raw) > max_upload_bytes():
        raise HTTPException(status_code=413, detail=f"File exceeds the configured {max_upload_bytes() // (1024 * 1024)} MiB limit.")

    try:
        if suffix == ".csv":
            # Keep identifiers such as account numbers as strings. Analyse only a capped number of rows.
            frame = pd.read_csv(io.BytesIO(raw), dtype=str, keep_default_na=False, nrows=max_analysis_rows() + 1, encoding_errors="replace")
            source_format = "csv"
        else:
            workbook = pd.ExcelFile(io.BytesIO(raw))
            if not workbook.sheet_names:
                raise HTTPException(status_code=400, detail="The workbook contains no sheets.")
            selected_sheet = sheet_name or workbook.sheet_names[0]
            if selected_sheet not in workbook.sheet_names:
                raise HTTPException(status_code=400, detail="The selected workbook sheet does not exist.")
            frame = pd.read_excel(workbook, sheet_name=selected_sheet, dtype=str, keep_default_na=False, nrows=max_analysis_rows() + 1)
            source_format = "excel"
    except HTTPException:
        raise
    except Exception as exc:
        # Do not expose parser internals or raw file contents.
        raise HTTPException(status_code=400, detail="Could not parse this file. Check that it is a valid CSV or Excel workbook.") from exc

    if frame.empty or len(frame.columns) == 0:
        raise HTTPException(status_code=400, detail="The file has no transaction rows or usable columns.")
    if len(frame) > max_analysis_rows():
        frame = frame.iloc[:max_analysis_rows()].copy()
        truncated = True
    else:
        truncated = False

    columns = [str(column).strip() for column in frame.columns]
    if any(not column or column.lower().startswith("unnamed:") for column in columns):
        raise HTTPException(status_code=400, detail="One or more column headers are empty. Rename those columns and upload again.")
    if len({column.casefold() for column in columns}) != len(columns):
        raise HTTPException(status_code=400, detail="Duplicate column names are not supported. Give each column a unique header.")
    frame.columns = columns
    metadata = {
        "filename": filename,
        "format": source_format,
        "sheet_name": sheet_name if source_format == "excel" else None,
        "row_count": int(len(frame)),
        "truncated": truncated,
        "sheet_names": workbook.sheet_names if suffix in {".xlsx", ".xls"} else [],
    }
    return frame, metadata


def _norm(value: Any) -> str:
    return " ".join(str(value).strip().lower().replace("_", " ").replace("-", " ").split())


def suggest_mapping(columns: list[str]) -> dict[str, str | None]:
    normalized = {_norm(column): column for column in columns}
    result: dict[str, str | None] = {}
    for field, aliases in ALIASES.items():
        selected = next((normalized[_norm(alias)] for alias in aliases if _norm(alias) in normalized), None)
        result[field] = selected
    return result


def infer_column_type(series: pd.Series) -> str:
    values = series.astype(str).str.strip()
    nonempty = values[values.ne("")]
    if nonempty.empty:
        return "empty"
    numeric = pd.to_numeric(nonempty, errors="coerce")
    if numeric.notna().mean() >= 0.85:
        return "numeric"
    dates = pd.to_datetime(nonempty.head(200), errors="coerce", utc=True, format="mixed")
    if dates.notna().mean() >= 0.75:
        return "datetime"
    return "text"


def build_preview(frame: pd.DataFrame, metadata: dict[str, Any]) -> dict[str, Any]:
    columns = []
    for name in frame.columns:
        series = frame[name].astype(str)
        nonempty = series[series.str.strip().ne("")]
        columns.append({
            "name": str(name),
            "inferred_type": infer_column_type(frame[name]),
            "null_count": int(series.str.strip().eq("").sum()),
            "sample_values": [str(v)[:100] for v in nonempty.head(3).tolist()],
        })
    rows = []
    for _, row in frame.head(PREVIEW_ROWS).iterrows():
        rows.append({str(k): (None if str(v).strip() == "" else str(v)[:300]) for k, v in row.items()})
    return {
        **metadata,
        "columns": columns,
        "preview_rows": rows,
        "mapping_suggestions": suggest_mapping([str(c) for c in frame.columns]),
        "warnings": ["The row count is capped by the configured analysis limit; later records were not examined."] if metadata.get("truncated") else [],
    }
