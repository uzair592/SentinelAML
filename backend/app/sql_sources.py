"""Request-scoped, bounded, read-only SQL metadata and table access."""
from __future__ import annotations

import ipaddress
import os
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import HTTPException
from sqlalchemy import MetaData, Table, create_engine, inspect, select
from sqlalchemy.engine import Engine, URL
from sqlalchemy.exc import SQLAlchemyError

from .ingestion import build_preview

SUPPORTED_ENGINES = {"postgresql", "mysql", "sqlite"}
BLOCKED_IPS = {"169.254.169.254", "100.100.100.200"}


def _allowed_hosts() -> set[str]:
    return {item.strip().lower().rstrip(".") for item in os.getenv("SENTINELAML_ALLOWED_DB_HOSTS", "").split(",") if item.strip()}


def _is_loopback(host: str) -> bool:
    value = host.strip().lower().rstrip(".")
    if value in {"localhost", "localhost.localdomain"}:
        return True
    try:
        return ipaddress.ip_address(value).is_loopback
    except ValueError:
        return False


def _validate_network_host(host: str | None) -> str:
    if not host:
        raise HTTPException(status_code=422, detail="A database host is required.")
    normalized = host.strip().lower().rstrip(".")
    if normalized in BLOCKED_IPS:
        raise HTTPException(status_code=403, detail="This database host is not allowed.")
    try:
        ip = ipaddress.ip_address(normalized)
        if ip.is_link_local or ip.is_unspecified or ip.is_multicast:
            raise HTTPException(status_code=403, detail="This database host is not allowed.")
    except ValueError:
        pass
    allowed = _allowed_hosts()
    environment = os.getenv("SENTINELAML_ENV", "development").lower()
    if normalized in allowed:
        return normalized
    if environment != "production" and _is_loopback(normalized):
        return normalized
    raise HTTPException(status_code=403, detail="Database host is not allowlisted. Configure SENTINELAML_ALLOWED_DB_HOSTS on the API server.")


def _sqlite_database_path(sqlite_path: str | None) -> Path:
    root = Path(os.getenv("SENTINELAML_SQLITE_ROOT", "./source-databases")).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    requested = Path(sqlite_path or "sample.db").expanduser()
    path = (root / requested).resolve() if not requested.is_absolute() else requested.resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="SQLite files must be inside the configured source database directory.") from exc
    if not path.is_file():
        raise HTTPException(status_code=404, detail="The SQLite database file does not exist in the approved directory.")
    return path


def create_source_engine(config: Any) -> Engine:
    dialect = str(config.engine).lower()
    if dialect not in SUPPORTED_ENGINES:
        raise HTTPException(status_code=422, detail="Unsupported database engine.")
    try:
        if dialect == "sqlite":
            path = _sqlite_database_path(config.sqlite_path)
            # SQLite URI mode=ro makes this connector genuinely read-only.
            url = URL.create(
                "sqlite+pysqlite",
                database=f"file:{path.as_posix()}",
                query={"mode": "ro", "uri": "true"},
            )
            return create_engine(url, connect_args={"timeout": 5}, pool_pre_ping=True)
        host = _validate_network_host(config.host)
        database = (config.database or "").strip()
        username = (config.username or "").strip()
        if not database or not username:
            raise HTTPException(status_code=422, detail="Database name and username are required.")
        port = config.port
        if port is not None and not (1 <= int(port) <= 65535):
            raise HTTPException(status_code=422, detail="Database port must be between 1 and 65535.")
        driver = "postgresql+psycopg" if dialect == "postgresql" else "mysql+pymysql"
        url = URL.create(
            driver,
            username=username,
            password=config.password or "",
            host=host,
            port=port,
            database=database,
        )
        if dialect == "postgresql":
            return create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 5}, pool_timeout=5)
        return create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 5}, pool_timeout=5)
    except HTTPException:
        raise
    except Exception as exc:
        # Do not leak connection strings, drivers' messages, or credentials.
        raise HTTPException(status_code=400, detail="The database connection settings are invalid.") from exc


def test_connection(config: Any) -> dict[str, Any]:
    engine = create_source_engine(config)
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("SELECT 1")
        return {"ok": True, "engine": str(config.engine).lower(), "message": "Connection successful. Credentials were used for this request only."}
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=502, detail="Connection failed. Verify the approved host, network access, database name, credentials, TLS settings and read-only permissions.") from exc
    finally:
        engine.dispose()


def list_source_tables(config: Any) -> dict[str, Any]:
    engine = create_source_engine(config)
    try:
        with engine.connect() as connection:
            inspector = inspect(connection)
            schemas = inspector.get_schema_names() if str(config.engine).lower() == "postgresql" else []
            tables = []
            if schemas:
                for schema in schemas:
                    if schema in {"pg_catalog", "information_schema"}:
                        continue
                    for table_name in inspector.get_table_names(schema=schema):
                        tables.append({"schema": schema, "name": table_name})
            else:
                for table_name in inspector.get_table_names():
                    tables.append({"schema": None, "name": table_name})
            return {"engine": str(config.engine).lower(), "tables": tables[:2_000], "truncated": len(tables) > 2_000}
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=502, detail="Could not list tables. Verify the database's read-only metadata permissions.") from exc
    finally:
        engine.dispose()


def read_source_table(config: Any, schema_name: str | None, table_name: str, requested_limit: int) -> tuple[pd.DataFrame, dict[str, Any]]:
    if not table_name or len(table_name) > 256 or "\x00" in table_name:
        raise HTTPException(status_code=422, detail="Invalid table name.")
    try:
        maximum = max(1, int(os.getenv("SENTINELAML_SQL_ROW_LIMIT", "5000")))
    except ValueError:
        maximum = 5000
    limit = min(max(int(requested_limit), 1), maximum)
    engine = create_source_engine(config)
    try:
        with engine.connect() as connection:
            inspector = inspect(connection)
            schema = schema_name or None
            if str(config.engine).lower() != "postgresql" and schema:
                raise HTTPException(status_code=422, detail="Schema selection is supported only for PostgreSQL in this version.")
            available = inspector.get_table_names(schema=schema)
            if table_name not in available:
                raise HTTPException(status_code=404, detail="The selected table was not found in the accessible schema.")
            metadata = MetaData()
            table = Table(table_name, metadata, schema=schema, autoload_with=connection)
            statement = select(table).limit(limit + 1)
            result = connection.execute(statement)
            rows = [dict(row._mapping) for row in result]
            truncated = len(rows) > limit
            rows = rows[:limit]
            # Preserve IDs as strings for mapping; numeric and time values retain display representation.
            frame = pd.DataFrame(rows, columns=list(table.columns.keys()))
            if not frame.empty:
                for column in frame.columns:
                    frame[column] = frame[column].map(lambda value: "" if value is None else str(value))
            source = {
                "kind": "sql",
                "engine": str(config.engine).lower(),
                "schema": schema,
                "table": table_name,
                "row_count": int(len(frame)),
                "truncated": truncated,
                "credentials_persisted": False,
            }
            return frame, source
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=502, detail="Could not read the selected table. Verify SELECT permissions and table compatibility.") from exc
    finally:
        engine.dispose()


def preview_source_table(config: Any, schema_name: str | None, table_name: str, limit: int) -> dict[str, Any]:
    frame, source = read_source_table(config, schema_name, table_name, limit)
    if frame.empty:
        raise HTTPException(status_code=400, detail="The selected table returned no rows.")
    return {
        **build_preview(frame, source),
        "mapping_suggestions": __import__("app.ingestion", fromlist=["suggest_mapping"]).suggest_mapping([str(c) for c in frame.columns]),
    }
