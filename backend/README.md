# SentinelAML Backend

## Local setup

Requirements: Python 3.11+ recommended.

```bash
cd backend
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS / Linux:
# source .venv/bin/activate
python -m pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

On macOS/Linux, use `cp .env.example .env` instead of `copy`. The API health check is `http://127.0.0.1:8000/api/health`; local OpenAPI docs are at `http://127.0.0.1:8000/docs`.

## Tests

```bash
python -m pytest
```

## SQL connector safety

- Local database hosts are accepted only in development by default.
- Remote PostgreSQL/MySQL hosts must be listed exactly in `SENTINELAML_ALLOWED_DB_HOSTS` on the API server.
- Production needs network-level egress controls as well as application host allowlisting.
- Use an approved read-only database account.
- SQLite files must exist inside `SENTINELAML_SQLITE_ROOT` and are opened in read-only mode.
- Connector credentials are supplied per request and are not saved by this app.
- Do not expose this development API to the public internet or use it with real customer data.

The starter connector intentionally does not offer arbitrary SQL input.
