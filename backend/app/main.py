"""SentinelAML API: authenticated ingestion, cases, policy retrieval and investigation."""
from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from typing import Any, Literal
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .analysis import analyze_dataframe
from .ingestion import build_preview, read_upload
from .investigation_agents import run_investigation
from .persistence import (
    AnalysisRun, CaseEvent, InvestigationCase, PolicyDocument, SessionLocal, User,
    decode_access_token, get_db, init_db, issue_access_token, log_audit,
    user_public, verify_password,
)
from .policy_service import ingest_policy_upload, list_policies, search_policies
from .sql_sources import list_source_tables, preview_source_table, read_source_table, test_connection


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="SentinelAML API",
    description="Authenticated AML data analysis, investigation cases and policy-grounded investigation workflows.",
    version="0.2.0",
    lifespan=lifespan,
)

origins = [item.strip() for item in os.getenv("SENTINELAML_CORS_ORIGINS", "http://127.0.0.1:5173").split(",") if item.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Content-Type", "Authorization"],
)

bearer = HTTPBearer(auto_error=False)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    errors = [{"field": ".".join(str(part) for part in item.get("loc", []) if part != "body"), "message": item.get("msg", "Invalid value")} for item in exc.errors()]
    return JSONResponse(status_code=422, content={"error": {"code": "VALIDATION_ERROR", "message": "The request contains invalid fields.", "details": errors}})


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: str = Field(min_length=1, max_length=2048)


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


class CaseCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    analysis_run_id: str = Field(min_length=1, max_length=80)
    alert_id: str = Field(min_length=1, max_length=160)
    title: str | None = Field(default=None, max_length=500)
    analyst_notes: str = Field(default="", max_length=10000)


class CaseUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["open", "in_review", "escalated", "closed"] | None = None
    disposition: Literal["pending", "no_concern_identified", "escalated_for_review", "reporting_consideration", "insufficient_information"] | None = None
    analyst_notes: str | None = Field(default=None, max_length=10000)
    assigned_to: str | None = Field(default=None, max_length=80)


class InvestigateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str | None = Field(default=None, max_length=1000)


class PolicySearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=3, max_length=1000)
    limit: int = Field(default=5, ge=1, le=10)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(status_code=401, detail="Sign in to access SentinelAML.", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = decode_access_token(credentials.credentials)
        user = db.get(User, payload.get("sub"))
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Access token is invalid or expired.", headers={"WWW-Authenticate": "Bearer"}) from exc
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User is not active.", headers={"WWW-Authenticate": "Bearer"})
    return user


def _parse_object(value: str, field_name: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except (json.JSONDecodeError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=f"{field_name} must be valid JSON.") from exc
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=422, detail=f"{field_name} must be a JSON object.")
    return parsed


def _save_analysis(db: Session, user: User, result: dict[str, Any], source_label: str, source_kind: str) -> dict[str, Any]:
    run = AnalysisRun(
        id=str(uuid4()),
        user_id=user.id,
        source_kind=source_kind,
        source_label=source_label[:240],
        result_json=result,
    )
    db.add(run)
    log_audit(db, user.id, "analysis.created", "analysis_run", run.id, {
        "source_kind": source_kind,
        "source_label": source_label[:120],
        "total_transactions": (result.get("summary") or {}).get("total_transactions", 0),
        "alert_count": (result.get("summary") or {}).get("alert_count", 0),
    })
    db.commit()
    result["analysis_run_id"] = run.id
    return result


def _can_access_case(case: InvestigationCase, user: User) -> bool:
    if user.role in {"admin", "compliance_officer", "supervisor", "auditor"}:
        return True
    return case.created_by == user.id or case.assigned_to == user.id


def _case_public(case: InvestigationCase, include_report: bool = False) -> dict[str, Any]:
    result = {
        "id": case.id,
        "case_reference": case.case_reference,
        "analysis_run_id": case.analysis_run_id,
        "alert_id": case.alert_id,
        "title": case.title,
        "severity": case.severity,
        "status": case.status,
        "disposition": case.disposition,
        "subject_reference": case.subject_reference,
        "alert_snapshot": case.alert_snapshot,
        "analyst_notes": case.analyst_notes,
        "created_at": case.created_at.isoformat() if case.created_at else None,
        "updated_at": case.updated_at.isoformat() if case.updated_at else None,
        "assigned_to": case.assigned_to,
        "created_by": case.created_by,
    }
    if include_report:
        result["investigation_report"] = case.investigation_report
    return result


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "SentinelAML API", "version": app.version}


@app.post("/api/auth/login")
def login(request: LoginRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    user = db.scalar(select(User).where(func.lower(User.email) == request.email.lower()))
    if not user or not user.is_active or not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")
    token = issue_access_token(user)
    log_audit(db, user.id, "auth.login", "user", user.id, {})
    db.commit()
    return {"access_token": token, "token_type": "bearer", "expires_in": 3600, "user": user_public(user)}


@app.get("/api/auth/me")
def auth_me(user: User = Depends(get_current_user)) -> dict[str, Any]:
    return user_public(user)


@app.get("/api/overview")
def overview(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    latest = db.scalar(select(AnalysisRun).where(AnalysisRun.user_id == user.id).order_by(AnalysisRun.created_at.desc()).limit(1))
    cases = db.scalars(select(InvestigationCase).where(InvestigationCase.created_by == user.id)).all()
    policies_count = db.scalar(select(func.count(PolicyDocument.id))) or 0
    analysis_result = latest.result_json if latest else None
    summary = (analysis_result or {}).get("summary", {})
    return {
        "user": user_public(user),
        "latest_analysis": {
            "id": latest.id, "source_label": latest.source_label, "source_kind": latest.source_kind,
            "created_at": latest.created_at.isoformat() if latest.created_at else None,
        } if latest else None,
        "summary": summary,
        "cases": {"total": len(cases), "open": sum(1 for item in cases if item.status == "open"),
                  "in_review": sum(1 for item in cases if item.status == "in_review"),
                  "escalated": sum(1 for item in cases if item.status == "escalated"),
                  "closed": sum(1 for item in cases if item.status == "closed")},
        "policy_documents": policies_count,
        "analytics_available": bool(latest),
    }


@app.post("/api/files/preview")
async def preview_file(
    file: UploadFile = File(...),
    sheet_name: str | None = Form(default=None),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    frame, metadata = await read_upload(file, sheet_name)
    return build_preview(frame, metadata)


@app.post("/api/files/analyze")
async def analyze_file(
    file: UploadFile = File(...),
    mapping: str = Form(...),
    options: str = Form(default="{}"),
    sheet_name: str | None = Form(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    mapping_obj = _parse_object(mapping, "mapping")
    options_obj = _parse_object(options, "options")
    frame, metadata = await read_upload(file, sheet_name)
    try:
        result = analyze_dataframe(frame, mapping_obj, options_obj, {"kind": "file", **metadata})
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_analysis(db, user, result, metadata.get("filename", "Uploaded file"), "file")


@app.post("/api/sql/test")
async def sql_test(request: DatabaseConnection, user: User = Depends(get_current_user)) -> dict[str, Any]:
    return test_connection(request)


@app.post("/api/sql/tables")
async def sql_tables(request: SqlTablesRequest, user: User = Depends(get_current_user)) -> dict[str, Any]:
    return list_source_tables(request)


@app.post("/api/sql/preview")
async def sql_preview(request: SqlTableRequest, user: User = Depends(get_current_user)) -> dict[str, Any]:
    return preview_source_table(request, request.schema_name, request.table_name, request.limit)


@app.post("/api/sql/analyze")
async def analyze_sql(
    request: SqlAnalyzeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    frame, source = read_source_table(request, request.schema_name, request.table_name, min(request.limit, 5000))
    if frame.empty:
        raise HTTPException(status_code=400, detail="The selected table returned no rows.")
    try:
        result = analyze_dataframe(frame, request.mapping, request.options, source)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_analysis(db, user, result, f"{source.get('engine')}:{source.get('table')}", "sql")


@app.get("/api/cases")
def list_cases(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    stmt = select(InvestigationCase).order_by(InvestigationCase.updated_at.desc()).limit(limit)
    if user.role not in {"admin", "compliance_officer", "supervisor", "auditor"}:
        stmt = select(InvestigationCase).where((InvestigationCase.created_by == user.id) | (InvestigationCase.assigned_to == user.id)).order_by(InvestigationCase.updated_at.desc()).limit(limit)
    cases = db.scalars(stmt).all()
    return {"cases": [_case_public(case) for case in cases]}


@app.post("/api/cases")
def create_case(
    request: CaseCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    analysis = db.get(AnalysisRun, request.analysis_run_id)
    if not analysis or (analysis.user_id != user.id and user.role not in {"admin", "compliance_officer", "supervisor", "auditor"}):
        raise HTTPException(status_code=404, detail="Analysis run was not found.")
    result = analysis.result_json
    alert = next((item for item in result.get("alerts", []) if item.get("alert_id") == request.alert_id), None)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert was not found in the specified analysis run.")
    case = InvestigationCase(
        id=str(uuid4()),
        case_reference="SAML-" + uuid4().hex[:10].upper(),
        created_by=user.id,
        assigned_to=user.id,
        analysis_run_id=analysis.id,
        alert_id=alert["alert_id"],
        title=(request.title or alert.get("title") or "AML review case")[:500],
        severity=alert.get("severity", "medium"),
        status="open",
        disposition="pending",
        subject_reference=alert.get("subject_reference"),
        alert_snapshot=alert,
        analyst_notes=request.analyst_notes,
    )
    db.add(case)
    db.flush()
    db.add(CaseEvent(case_id=case.id, actor_id=user.id, event_type="case.created", detail={"alert_id": case.alert_id, "severity": case.severity}))
    log_audit(db, user.id, "case.created", "investigation_case", case.id, {"case_reference": case.case_reference, "severity": case.severity})
    db.commit()
    return _case_public(case, include_report=True)


@app.get("/api/cases/{case_id}")
def get_case(case_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    case = db.get(InvestigationCase, case_id)
    if not case or not _can_access_case(case, user):
        raise HTTPException(status_code=404, detail="Investigation case was not found.")
    events = db.scalars(select(CaseEvent).where(CaseEvent.case_id == case.id).order_by(CaseEvent.created_at.asc())).all()
    return {
        **_case_public(case, include_report=True),
        "events": [{"event_type": event.event_type, "detail": event.detail, "created_at": event.created_at.isoformat(), "actor_id": event.actor_id} for event in events],
    }


@app.patch("/api/cases/{case_id}")
def update_case(
    case_id: str,
    request: CaseUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    case = db.get(InvestigationCase, case_id)
    if not case or not _can_access_case(case, user):
        raise HTTPException(status_code=404, detail="Investigation case was not found.")
    changes: dict[str, Any] = {}
    for key in ("status", "disposition", "analyst_notes", "assigned_to"):
        value = getattr(request, key)
        if value is not None:
            if key == "assigned_to":
                target = db.get(User, value)
                if not target or not target.is_active:
                    raise HTTPException(status_code=422, detail="Assigned user does not exist or is inactive.")
                if user.role not in {"admin", "compliance_officer", "supervisor"}:
                    raise HTTPException(status_code=403, detail="Only a supervisor or administrator can reassign a case.")
            old = getattr(case, key)
            setattr(case, key, value)
            changes[key] = {"from": old, "to": value}
    if changes:
        db.add(CaseEvent(case_id=case.id, actor_id=user.id, event_type="case.updated", detail=changes))
        log_audit(db, user.id, "case.updated", "investigation_case", case.id, {"fields_changed": sorted(changes)})
        db.commit()
        db.refresh(case)
    return _case_public(case, include_report=True)


@app.post("/api/cases/{case_id}/investigate")
def investigate_case(
    case_id: str,
    request: InvestigateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    case = db.get(InvestigationCase, case_id)
    if not case or not _can_access_case(case, user):
        raise HTTPException(status_code=404, detail="Investigation case was not found.")
    analysis = db.get(AnalysisRun, case.analysis_run_id)
    if not analysis:
        raise HTTPException(status_code=409, detail="The linked analysis run is unavailable.")
    workflow = run_investigation(db, case, analysis.result_json, request.question)
    case.investigation_report = workflow
    if case.status == "open":
        case.status = "in_review"
    db.add(CaseEvent(case_id=case.id, actor_id=user.id, event_type="case.investigation_generated", detail={
        "workflow": workflow["workflow"], "agent_count": len(workflow["agents"]),
        "report_mode": workflow["report"]["mode"], "policy_passages": len(workflow["report"].get("policy_citations", [])),
    }))
    log_audit(db, user.id, "case.investigation_generated", "investigation_case", case.id, {
        "report_mode": workflow["report"]["mode"], "policy_passages": len(workflow["report"].get("policy_citations", [])),
    })
    db.commit()
    db.refresh(case)
    return {"case": _case_public(case, include_report=True), "workflow": workflow}


@app.get("/api/policies")
def policies(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    return {"documents": list_policies(db)}


@app.post("/api/policies/upload")
async def upload_policy(
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    if user.role not in {"admin", "compliance_officer", "supervisor"}:
        raise HTTPException(status_code=403, detail="Only compliance personnel can add policy documents.")
    result = await ingest_policy_upload(file, db, user.id, title)
    log_audit(db, user.id, "policy.uploaded", "policy_document", result["id"], {"title": result["title"], "chunk_count": result["chunk_count"]})
    db.commit()
    return result


@app.post("/api/policies/search")
def policy_search(request: PolicySearchRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    return {"query": request.query, "retrieval_method": "transparent lexical overlap baseline", "results": search_policies(db, request.query, request.limit)}


@app.get("/api/audit")
def audit_events(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    if user.role not in {"admin", "compliance_officer", "supervisor", "auditor"}:
        raise HTTPException(status_code=403, detail="Audit events require an authorized compliance role.")
    from .persistence import AuditEvent
    events = db.scalars(select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(limit)).all()
    return {"events": [{
        "id": event.id, "actor_id": event.actor_id, "action": event.action,
        "resource_type": event.resource_type, "resource_id": event.resource_id,
        "metadata": event.metadata_json, "created_at": event.created_at.isoformat(),
    } for event in events]}
