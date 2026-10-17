# SentinelAML Roadmap

## Milestone 0 — Foundation and blueprint
- [x] Establish product goal, constraints, architecture, flow diagram, ERD, rules, security model, and API contract.
- [x] Add repository conventions, local setup, environment examples, and CI.

## Milestone 1 — Ingestion-first working prototype
- [x] React portal with navigation, overview dashboard and data-source workflow.
- [x] CSV/XLSX preview, file validation, sheet selection and column mapping.
- [x] Shared canonical schema and validation reports.
- [x] Deterministic KPIs and currency-separated totals.
- [x] Initial explainable rules with exact evidence row references.
- [x] Results table with alert detail panels and CSV export.\n- [ ] Add alert search/severity filters and JSON export.
- [x] Unit tests and synthetic sample data.

**Acceptance:** User can choose a sample/own CSV or XLSX, review the inferred columns, map required fields, run analysis, and see repeatable KPIs and evidence-backed alerts.

## Milestone 2 — SQL connector
- [x] Select supported database engine.
- [x] Request-scoped credentials and secure form behavior.
- [x] Host allowlisting, connection timeouts and driver validation.\n- [ ] Add database-specific statement timeouts and stronger TLS configuration.
- [x] Test connection and list accessible tables.
- [x] Preview columns and capped row sample.
- [x] Map fields and analyze with the same engine.
- [ ] Tests for disallowed hosts, drivers, paths, missing tables, and timeout failures.

**Acceptance:** A dedicated read-only SQL account can be tested against an approved development source; table import is bounded and no credentials are persisted or logged.

## Milestone 3 — Investigation workspace
- [ ] Alert detail view and transaction timeline.
- [ ] Evidence panel with calculation details and source row references.
- [ ] Analyst notes, disposition, assignment and case history.
- [ ] Versioned rule configurations and reproducible exports.

## Milestone 4 — Agentic investigation
- [ ] Stateful orchestrator with typed, allowlisted tools.
- [ ] Evidence-first plan: gather transactions, compute statistics, retrieve approved policies, produce a sourced draft.
- [ ] Retry, timeout, token-budget and bounded-step safeguards.
- [ ] Human approval checkpoint for case actions.
- [ ] Evaluation set for groundedness, tool correctness and safe escalation.

## Milestone 5 — Policy knowledge base and governance
- [ ] Ingest approved public policies and institution-approved procedures.
- [ ] Metadata, document hash, source URL, publication/version date and chunk citations.
- [ ] Tests for stale sources, conflicting guidance and prompt injection.
- [ ] Model/rule cards, limitations, monitoring and change management.

## Milestone 6 — Hardening
- [ ] Authentication, MFA/SSO integration, RBAC, organization/tenant isolation.
- [ ] Production secrets, database TLS, egress restrictions, encryption and retention.
- [ ] Background workers and scalable storage for large data sources.
- [ ] CI, dependency scanning, security testing and independent review.
- [ ] Bank-specific validation and formally approved operational procedures.

## Definition of done for every milestone

- Code has automated tests and clear setup notes.
- No credentials or real customer data are committed.
- Errors are actionable but do not reveal secrets.
- Architecture and API docs match behavior.
- Detection results describe observed patterns rather than asserting criminality.
- No consequential account or regulatory action happens without authorized human approval.
