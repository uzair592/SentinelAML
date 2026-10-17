# SentinelAML

**Agentic AI Fraud & Anti-Money Laundering (AML) Investigation Workbench**

SentinelAML is an early-stage prototype for helping financial-crime analysts explore transaction data, detect explainable risk indicators, and prepare evidence-backed cases for human review. It is being designed for bank evaluation using synthetic or explicitly authorized data.

> **Prototype notice:** SentinelAML is not a production banking control, legal/compliance advice, or a substitute for a bank's approved AML program. Detection rules are configurable analytical heuristics, not legal thresholds. Human review is required for consequential decisions.

## Product goals

- Import transaction data from CSV and Excel files, preview it, map columns, validate data quality, and run analyses.
- Connect to a supported SQL database using a dedicated read-only database account, inspect tables, and import a capped sample.
- Calculate data-quality and transaction KPIs; surface explainable anomalies and possible patterns for analyst review.
- Keep evidence and reasoning traceable to source rows, rather than producing unsupported AI conclusions.
- Evolve toward case management, policy-grounded retrieval, agent orchestration, role-based access, and auditable human approvals.

## Architecture at a glance

- **Frontend:** React + TypeScript + Vite.
- **API and ingestion:** Python + FastAPI + pandas.
- **SQL access:** SQLAlchemy with explicitly supported drivers and bounded, table-based imports (no arbitrary SQL editor).
- **Initial analysis:** deterministic, explainable rules and robust statistical profiling.
- **Future agent layer:** a stateful workflow with constrained tools, policy retrieval, approval checkpoints, and audit events.

See [the project blueprint](docs/PROJECT_BLUEPRINT.md), [architecture](docs/ARCHITECTURE.md), [ERD](docs/ERD.md), [ingestion and SQL connectors](docs/INGESTION_AND_CONNECTORS.md), [AML rule catalogue](docs/AML_RULE_CATALOG.md), [security model](docs/SECURITY.md), [API contract](docs/API_CONTRACT.md), and [roadmap](docs/ROADMAP.md).

## Planned local development

Once the application scaffold is checked in:

1. Start the Python API from `backend/`.
2. Start the Vite frontend from `frontend/`.
3. Open the local web UI, upload a synthetic CSV/XLSX transaction file, map columns, and analyze it.
4. Or configure a supported SQL source for a connectivity check, table discovery, and bounded sample import.

Exact setup commands will be documented here as implementation lands.

## Initial transaction fields

The analyzer expects mapped source columns for at least:

- transaction timestamp
- transaction amount
- source/origin account identifier

Transaction ID, destination account, customer ID, currency, transaction type, channel, and status are optional but improve analysis. Column names can vary; users should map their file's columns in the UI.

## Safety and data handling

- Start with synthetic datasets; do not upload real customer or account data to an unapproved environment.
- Use dedicated, least-privilege read-only SQL credentials and restrict network access to approved hosts.
- Database passwords must not be logged or stored in source control. Never expose database credentials to the browser after submission.
- Keep data volumes capped, validate files and schemas, and treat uploaded text as untrusted.
- Findings indicate patterns requiring review. They do not prove criminality or automatically trigger account restrictions or regulatory submissions.

## Status

**Stage 0 — Blueprint and initial ingestion MVP in progress.** See [roadmap](docs/ROADMAP.md) for deliverables and acceptance criteria.
