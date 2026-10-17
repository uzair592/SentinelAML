# SentinelAML

**Agentic AI Fraud & Anti-Money Laundering Investigation Workbench**

SentinelAML is an early-stage analyst-assistance prototype for profiling financial transaction data, surfacing explainable AML risk indicators, and preparing evidence for human review.

> **Prototype notice:** This is not a production banking control, regulatory certification, or legal advice. The initial detection rules are configurable analytical heuristics, not regulator-prescribed thresholds. An alert is not proof of wrongdoing.

## Current implementation

- Responsive React + TypeScript analyst portal.
- CSV, XLSX and XLS preview, schema inference, and required/optional column mapping.
- Transaction metrics, data-quality findings and evidence-linked alerts.
- Initial rules: high-value transactions, transaction velocity, possible structuring patterns, robust amount outliers, duplicate transaction identifiers.
- Currency-separated aggregates; mixed currencies are never summed together.
- PostgreSQL and MySQL/MariaDB SQL connection testing, table discovery, bounded preview and analysis.
- Local SQLite sources restricted to an approved directory and opened read-only.
- SQL credentials are sent request-by-request and are not persisted by the app.
- Synthetic sample dataset, starter tests, CI, project flow diagrams, ERD and security documentation.

## Architecture

- Frontend: React, TypeScript and Vite.
- API: FastAPI.
- Analytics: pandas and deterministic, explainable rules.
- SQL: SQLAlchemy with request-scoped credentials, allowlisted hosts and bounded table reads.
- Future: constrained stateful investigation agents, approved-policy retrieval, case management, RBAC and audit persistence.

## Run locally

### 1. Start the backend

Python 3.11+ recommended. In a terminal:

```bash
cd backend
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
# Windows PowerShell: Copy-Item .env.example .env\n# macOS/Linux: cp .env.example .env
uvicorn app.main:app --reload --env-file .env --host 127.0.0.1 --port 8000
```

Health check: http://127.0.0.1:8000/api/health  
Interactive API docs: http://127.0.0.1:8000/docs

### 2. Start the frontend in a second terminal

```bash
cd frontend
npm install
npm run dev
```

Open http://127.0.0.1:5173.

### 3. Try the synthetic sample

Upload `backend/sample_data/synthetic_transactions.csv`. Confirm the detected mapping for transaction timestamp, amount and source account, then select **Analyze transactions**. The sample contains synthetic review patterns only.

### 4. Run backend tests

```bash
cd backend
python -m pytest
```

## SQL connector safety

- Use a dedicated read-only SQL account.
- Localhost database connections are permitted in development. Remote hosts must be exact entries in `SENTINELAML_ALLOWED_DB_HOSTS` on the API server.
- In production, configure network-level egress restrictions, TLS/certificate verification, secrets handling, and approved database hosts.
- SQLite reads only existing files under `SENTINELAML_SQLITE_ROOT` (default `./source-databases` relative to the backend working directory).
- Never commit secrets or use real bank customer data without written authorization and approved controls.
- The API offers table discovery and bounded reflection-based reads, not arbitrary SQL execution.

See [docs/INGESTION_AND_CONNECTORS.md](docs/INGESTION_AND_CONNECTORS.md) and [docs/SECURITY.md](docs/SECURITY.md).

## Blueprint and diagrams

- [Product blueprint and project flow](docs/PROJECT_BLUEPRINT.md)
- [Architecture](docs/ARCHITECTURE.md)
- [ERD](docs/ERD.md)
- [Canonical data dictionary](docs/DATA_DICTIONARY.md)
- [AML rule catalogue](docs/AML_RULE_CATALOG.md)
- [API contract](docs/API_CONTRACT.md)
- [Security and privacy](docs/SECURITY.md)
- [Roadmap](docs/ROADMAP.md)

## Next milestones and limitations

The current code is an ingestion-first prototype, not yet a complete agentic AI system. Stateful investigation agents, approved-policy RAG, persistent cases, authentication/RBAC, multi-tenant isolation, stronger audit storage, background jobs and bank-specific validation remain future milestones.

Use synthetic or explicitly authorized data only. No alert automatically blocks an account, moves funds, or submits a regulatory report.
