"""Persistent SentinelAML metadata, authentication and case records.

Raw imported transaction tables are not copied into this database. Analysis summaries and
alert evidence are persisted so an authorized analyst can open a durable investigation.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import jwt
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "app_users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(160), default="Sentinel Analyst")
    role: Mapped[str] = mapped_column(String(40), default="analyst")
    password_hash: Mapped[str] = mapped_column(String(256))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    source_kind: Mapped[str] = mapped_column(String(40), default="file")
    source_label: Mapped[str] = mapped_column(String(240), default="Imported dataset")
    result_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class InvestigationCase(Base):
    __tablename__ = "investigation_cases"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    case_reference: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    assigned_to: Mapped[str | None] = mapped_column(ForeignKey("app_users.id"), nullable=True, index=True)
    analysis_run_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.id"), index=True)
    alert_id: Mapped[str] = mapped_column(String(160), index=True)
    title: Mapped[str] = mapped_column(String(500))
    severity: Mapped[str] = mapped_column(String(20), default="medium")
    status: Mapped[str] = mapped_column(String(32), default="open", index=True)
    disposition: Mapped[str | None] = mapped_column(String(80), nullable=True)
    subject_reference: Mapped[str | None] = mapped_column(String(240), nullable=True)
    alert_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    investigation_report: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    analyst_notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class CaseEvent(Base):
    __tablename__ = "case_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    case_id: Mapped[str] = mapped_column(ForeignKey("investigation_cases.id"), index=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(80))
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class PolicyDocument(Base):
    __tablename__ = "policy_documents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    created_by: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    file_name: Mapped[str] = mapped_column(String(240))
    source_url: Mapped[str | None] = mapped_column(String(1500), nullable=True)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class PolicyChunk(Base):
    __tablename__ = "policy_chunks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    document_id: Mapped[str] = mapped_column(ForeignKey("policy_documents.id"), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("app_users.id"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(100), index=True)
    resource_type: Mapped[str] = mapped_column(String(80))
    resource_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


def _database_url() -> str:
    configured = os.getenv("SENTINELAML_DATABASE_URL")
    if configured:
        return configured
    path = Path(os.getenv("SENTINELAML_DB_PATH", "./sentinelaml.db")).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    return "sqlite:///" + str(path.resolve())


DATABASE_URL = _database_url()
_connect_args = {"check_same_thread": False, "timeout": 15} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=Session)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    derived = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=16384, r=8, p=1, dklen=64)
    return "scrypt$16384$8$1$" + salt.hex() + "$" + derived.hex()


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, n, r, p, salt_hex, digest_hex = stored.split("$")
        if algorithm != "scrypt":
            return False
        expected = bytes.fromhex(digest_hex)
        computed = hashlib.scrypt(password.encode("utf-8"), salt=bytes.fromhex(salt_hex), n=int(n), r=int(r), p=int(p), dklen=len(expected))
        return hmac.compare_digest(computed, expected)
    except (ValueError, TypeError):
        return False


def jwt_secret() -> str:
    environment = os.getenv("SENTINELAML_ENV", "development").lower()
    secret = os.getenv("SENTINELAML_JWT_SECRET", "")
    if environment == "production":
        lowered = secret.lower()
        if len(secret) < 32 or any(marker in lowered for marker in ("replace-with", "change-me", "development-only", "unsafe-secret")):
            raise RuntimeError("Production requires a randomly generated SENTINELAML_JWT_SECRET of at least 32 characters; example secrets are rejected.")
        return secret
    return secret or "local-development-only-change-before-deployment-unsafe-secret"


def init_db() -> None:
    environment = os.getenv("SENTINELAML_ENV", "development").lower()
    email = os.getenv("SENTINELAML_ADMIN_EMAIL", "").strip().lower()
    password = os.getenv("SENTINELAML_ADMIN_PASSWORD", "")
    if environment == "production" and (
        not email
        or len(password) < 14
        or email == "sentinel.admin@example.com"
        or password == "ChangeThis-LocalOnly-123!"
    ):
        raise RuntimeError("Production startup requires a non-example SENTINELAML_ADMIN_EMAIL and a strong, non-example SENTINELAML_ADMIN_PASSWORD of at least 14 characters.")
    if environment == "production":
        jwt_secret()
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        first_user = db.scalar(select(User.id).limit(1))
        if first_user is None:
            if not email:
                email = "sentinel.admin@example.com"
            if not password and environment != "production":
                password = "ChangeThis-LocalOnly-123!"
            if not password:
                raise RuntimeError("Configure SENTINELAML_ADMIN_PASSWORD before initializing the first user.")
            db.add(User(email=email, display_name="Sentinel AML Administrator", role="admin", password_hash=hash_password(password)))
            db.commit()


def issue_access_token(user: User, minutes: int = 60) -> str:
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user.id,
        "email": user.email,
        "role": user.role,
        "iat": now,
        "exp": now + timedelta(minutes=minutes),
        "iss": "sentinelaml",
        "aud": "sentinelaml-web",
    }
    return jwt.encode(payload, jwt_secret(), algorithm="HS256")


def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, jwt_secret(), algorithms=["HS256"], issuer="sentinelaml", audience="sentinelaml-web")


def user_public(user: User) -> dict[str, Any]:
    return {"id": user.id, "email": user.email, "display_name": user.display_name, "role": user.role, "is_active": user.is_active}


def log_audit(db: Session, actor_id: str | None, action: str, resource_type: str, resource_id: str | None = None, metadata_json: dict[str, Any] | None = None) -> None:
    db.add(AuditEvent(actor_id=actor_id, action=action, resource_type=resource_type, resource_id=resource_id, metadata_json=metadata_json or {}))
