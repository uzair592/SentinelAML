"""SentinelAML API: file ingestion, profiling, and request-scoped SQL analysis."""
from __future__ import annotations

import json
import os
from typing import Any, Literal

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from .analysis import analyze_dataframe
from .ingestion import build_preview, read_upload
from .sql_sources import list_source_tables, preview_source_table, read_source_table, test_connection

app = FastAPI(
    title="SentinelAML API",
    description="Explainable AML data profiling and analyst-assistance prototype.",
    version="0.1.0",
)

origins = [item.strip() for item in os.getenv("SENTINELAML_CORS_ORIGINS", "http://localhost:5173").split(",") if item.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError):
    # Pydantic validation errors can include submitted values; omit them to avoid credential leakage.
    errors = [{"field": ".".join(str(part) for part in item.get("loc", []) if part != "body"), "message": item.get("msg", "Invalid value")} for item in exc.errors()]
    return JSONResponse(status_code=422, content={"error": {"code": "VALIDATION_ERROR", "message": "The request contains invalid fields.", "details": errors}})


class DatabaseConnection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    engine: Literal["postgresql", "mysql", "sqlite"]
    host: str | None = Field(default=None, max_length=255)
    port: int | None = Field(default=None, ge=1, le=65535)
    database: str | None = Field(default=None, max_length=255)
    username: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, max_length=2048)
    sqlite_path: str | None = Field(default=None, max_length=500)


class SqlTablesRequest(DatabaseConnection):
    pass


class SqlTableRequest(DatabaseConnection):
    model_config = ConfigDict(extra="forbid")
    schema_name: str | None = Field(default=None, max_length=255)
    table_name: str = Field(min_length=1, max_length=256)
    limit: int = Field(default=500, ge=1, le=100000)


class SqlAnalyzeRequest(SqlTableRequest):
    mapping: dict[str, str | None]
    options: dict[str, Any] = Field(default_factory=dict)


def _parse_object(value: str, field_name: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except (json.JSONDecodeError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=f"{field_name} must be valid JSON.") from exc
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=422, detail=f"{field_name} must be a JSON object.")
    return parsed


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "SentinelAML API", "version": app.version}


@app.post("/api/files/preview")
async def preview_file(file: UploadFile = File(...), sheet_name: str | None = Form(default=None)) -> dict[str, Any]:
    frame, metadata = await read_upload(file, sheet_name)
    return build_preview(frame, metadata)


@app.post("/api/files/analyze")
async def analyze_file(
    file: UploadFile = File(...),
    mapping: str = Form(...),
    options: str = Form(default="{}"),
    sheet_name: str | None = Form(default=None),
) -> dict[str, Any]:
    mapping_obj = _parse_object(mapping, "mapping")
    options_obj = _parse_object(options, "options")
    frame, metadata = await read_upload(file, sheet_name)
    try:
        result = analyze_dataframe(frame, mapping_obj, options_obj, {"kind": "file", **metadata})
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return result


@app.post("/api/sql/test")
async def sql_test(request: DatabaseConnection) -> dict[str, Any]:
    return test_connection(request)


@app.post("/api/sql/tables")
async def sql_tables(request: SqlTablesRequest) -> dict[str, Any]:
    return list_source_tables(request)


@app.post("/api/sql/preview")
async def sql_preview(request: SqlTableRequest) -> dict[str, Any]:
    return preview_source_table(request, request.schema_name, request.table_name, request.limit)


@app.post("/api/sql/analyze")
async def analyze_sql(request: SqlAnalyzeRequest) -> dict[str, Any]:
    frame, source = read_source_table(request, request.schema_name, request.table_name, request.limit)
    if frame.empty:
        raise HTTPException(status_code=400, detail="The selected table returned no rows.")
    try:
        return analyze_dataframe(frame, request.mapping, request.options, source)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
