# SentinelAML

**Agentic AI Fraud & AML Investigation Workbench**

SentinelAML helps compliance analysts profile transaction exports, review explainable risk indicators, search approved policy material, and prepare investigation drafts for human review.

> **Prototype limitation:** This is not a production banking control or regulatory certification. Detection thresholds are configurable heuristics, not regulator-prescribed limits. A flagged pattern does not establish criminality.

## Current capabilities

- Dark, responsive AML command-center dashboard with KPI cards, risk distribution visuals, alert explorer, case queue, policy intelligence and audit activity.
- CSV/XLSX/XLS ingestion with preview, schema inference and confirmed field mapping.
- Deterministic metrics, quality checks, currency-separated totals and evidence-linked rules.
- Alert rules for high-value transactions, transaction velocity, possible structuring, account-level amount outliers and duplicate transaction IDs.
- PostgreSQL/MySQL/MariaDB read-only connector workflow and bounded SQLite reads within an approved local directory.
- JWT sign-in for protected API routes; salted scrypt password hashes.
- Persistent local investigation cases, case events, report snapshots and application audit events.
- Approved policy ingestion for text PDF, TXT and Markdown documents with source-linked lexical retrieval.
- A bounded, four-role investigation workflow: Planner, Evidence Analyst, Policy Retrieval Agent and Report Synthesis Agent.
- Optional external LLM-assisted report drafting. It is **off by default**; only enable it after security/legal approval.
- Synthetic sample transactions and GitHub Actions checks.

## Architecture

- **Frontend:** React, TypeScript, Vite.
- **API:** FastAPI and Pydantic.
- **Analytics:** pandas with deterministic, explainable rules.
- **Metadata persistence:** SQLAlchemy; SQLite by default for local development, configurable database URL for approved deployments.
- **Policy retrieval:** locally stored document chunks and transparent lexical overlap ranking. Semantic/vector retrieval is a future enhancement.
- **Agent workflow:** bounded orchestration with constrained evidence/policy inputs and mandatory human review.

## Run locally

Python 3.11+ and Node.js 22+ are recommended.

### 1. Start the backend

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

macOS/Linux:
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --env-file .env --host 127.0.0.1 --port 8000
```

Local health check: http://127.0.0.1:8000/api/health  
API documentation: http://127.0.0.1:8000/docs

### 2. Start the frontend in a second terminal

```bash
cd frontend
npm install
npm run dev
```

Open http://127.0.0.1:5173.

### 3. Local prototype sign-in

With a fresh development database and the unchanged sample `.env.example`, sign in using:

- Email: `sentinel.admin@example.com`
- Password: `ChangeThis-LocalOnly-123!`

Change these local-only credentials in `.env` for your own environment. Never expose the default credentials or development server to a network. The UI shows synthetic demo metrics until you upload and analyze your own authorized dataset.

### 4. Try the synthetic sample and cases

Upload `backend/sample_data/synthetic_transactions.csv`, inspect the column mapping, and run analysis. Open an alert and select **Create investigation case**. Go to **Investigations** and run the four-agent workflow. Add an approved text-based policy under **Policy Intelligence** to see retrieved passages and citations in later drafts.

### 5. Run automated checks

```bash
cd backend
python -m pytest
```

In a separate terminal:
```bash
cd frontend
npm install
npm run build
```

## SQL and data-handling safety

- Use synthetic or explicitly authorized data only.
- The source transaction data is analyzed in memory and not stored as raw transaction rows by default. Analysis summaries and alert snapshots are persisted to support case continuity.
- Policy document text chunks, case notes, analysis metadata and audit events are persisted in the application database.
- Use a dedicated read-only source database user. Remote SQL hosts must be explicitly allowlisted on the backend; production needs network egress restrictions and approved TLS/secrets configuration as well.
- SQLite source files must stay within `SENTINELAML_SQLITE_ROOT`.
- The web client keeps its access token in memory only; reloading the page requires signing in again.
- External LLM support is disabled unless explicitly configured. Never enable it for bank data until institution security, legal, privacy and contractual approval is documented.
- No alert freezes accounts, moves funds, or automatically submits a regulatory report.

See the [project blueprint](docs/PROJECT_BLUEPRINT.md), [architecture](docs/ARCHITECTURE.md), [ERD](docs/ERD.md), [data dictionary](docs/DATA_DICTIONARY.md), [rule catalogue](docs/AML_RULE_CATALOG.md), [API contract](docs/API_CONTRACT.md), [security model](docs/SECURITY.md), and [roadmap](docs/ROADMAP.md).

## Production gap

This remains a local MVP. Before bank use, implement and validate institutional SSO/MFA, full role and tenant authorization, database TLS/timeouts and secrets management, encryption and retention controls, tamper-evident auditing, background jobs, semantic policy retrieval, model evaluation, security testing, and bank-specific compliance approval.
