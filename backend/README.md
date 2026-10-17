# SentinelAML Backend

## Local setup

Requirements: Python 3.11+ recommended.

Windows PowerShell:
```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload --env-file .env --host 127.0.0.1 --port 8000
```

macOS/Linux: use `source .venv/bin/activate` and `cp .env.example .env` instead of the PowerShell commands.

For a fresh local development database, the sample environment defaults to:
- Email: `sentinel.admin@example.com`
- Password: `ChangeThis-LocalOnly-123!`

These credentials are for localhost demonstrations only. Change them before any network exposure. Production mode requires a strong `SENTINELAML_ADMIN_PASSWORD` and a configured `SENTINELAML_JWT_SECRET` of at least 32 characters. Use a proper secrets manager for production.

Health check: `http://127.0.0.1:8000/api/health`  
OpenAPI docs: `http://127.0.0.1:8000/docs`

## Tests

```bash
python -m pytest
```

The suite covers health/auth, CSV preview and analysis, case persistence, multi-agent investigation drafting, policy ingestion/search, audit events, field mapping, analysis rules, and SQL-host policy checks.

## Persistence and AI configuration

- Local SQLAlchemy metadata defaults to `./sentinelaml.db` relative to the backend working directory.
- To use an approved application database, configure `SENTINELAML_DATABASE_URL` in the backend environment, for example an approved PostgreSQL URL with the Psycopg driver.
- Source transaction rows and SQL credentials are not persisted by default. Analysis summary/alert snapshots, cases, policy text chunks and audit event records are persisted.
- External LLM synthesis is disabled by default. It requires `SENTINELAML_LLM_PROVIDER=openai` and `OPENAI_API_KEY`. Do not enable it for sensitive banking data until institution security, privacy, legal and contractual approval is documented.

## SQL connector safety

- Local database hosts are accepted only in development by default.
- Remote PostgreSQL/MySQL hosts must be listed exactly in `SENTINELAML_ALLOWED_DB_HOSTS` on the API server.
- Production needs network-level egress controls, enforced TLS/certificate verification, strong timeouts and controlled secrets in addition to application-level allowlisting.
- Use an approved read-only database account.
- SQLite source files must exist inside `SENTINELAML_SQLITE_ROOT` and are opened in read-only mode.
- Connector credentials are supplied per request and are not saved by this app.
- Do not expose the development API to the public internet or use it with real customer data.

The connector does not offer arbitrary SQL execution. The current audit records are stored in the ordinary application database and are not tamper-evident or regulator-certified.
