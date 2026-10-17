# SentinelAML Roadmap

## Milestone 0 — Foundation and blueprint
- [x] Product goal, architecture, flow diagrams, ERD, canonical schema, rule catalogue, security baseline and API contract.
- [x] Repository setup instructions, synthetic data, starter tests and GitHub Actions CI.

## Milestone 1 — Ingestion and analytics
- [x] Responsive React dashboard and data-source workflow.
- [x] CSV/XLSX/XLS preview, validation, sheet selection and field mapping.
- [x] Shared canonical transaction model, KPIs and currency-separated totals.
- [x] Explainable deterministic rules with source row references.
- [x] Alert detail panel and formula-safe CSV alert export.
- [x] API and unit tests for upload and core analysis.

## Milestone 2 — SQL source connectors
- [x] Request-scoped credentials, host allowlisting, engine checks and timeouts.
- [x] Connection test, accessible table discovery, bounded preview and same-engine analysis.
- [x] Host policy unit tests.
- [ ] Database integration tests for driver permutations, statement timeout and TLS enforcement.
- [ ] Harden database-specific timeouts and certificate policy before bank use.

## Milestone 3 — Persistent investigation workspace
- [x] Authenticated API routes and local development sign-in.
- [x] Persistent analysis metadata and evidence-backed case snapshots.
- [x] Case creation, list/detail, notes, status, disposition and event history.
- [x] Application audit events for sign-in, analysis, case updates and policy upload.
- [ ] Full user administration, assignment UX, comments/attachments and supervisor approval screens.
- [ ] Institutional SSO/MFA, full RBAC review and tenant isolation.

## Milestone 4 — Bounded multi-agent investigation
- [x] Four-step workflow: planner, evidence analyst, policy retrieval, report synthesis.
- [x] Rule-aware review questions, evidence and data-quality context, limitations, and human-review draft.
- [x] Safe deterministic report fallback when an external model is unavailable.
- [x] Optional externally hosted LLM report drafting, disabled by default, with account-field minimization and citation-ID validation.
- [ ] Persistent workflow checkpointing, retries, idempotency, per-step audit detail and deeper transaction evidence tools.
- [ ] Evaluate grounding, citation correctness, safe refusal and usefulness with a labeled investigation test set.
- [ ] Add model/provider governance and formal approval controls before processing institution data.

## Milestone 5 — Policy knowledge base
- [x] Authorized PDF/TXT/Markdown ingestion, SHA-256 duplicate tracking and persisted text chunks.
- [x] Lexical retrieval with document and page/section references.
- [x] Policy search UI and citation display in the investigation workspace.
- [ ] Semantic embeddings/vector retrieval, version dates, amendment linking and conflict detection.
- [ ] Ingest and validate official policy sources; confirm currentness and institution applicability.
- [ ] Prompt-injection, stale-source and retrieval-quality tests.

## Milestone 6 — Modern command-center dashboard
- [x] Dark Power BI-inspired dashboard with KPI cards, trend sparkline panels, risk distribution, alert tables and status panels.
- [x] Clearly labeled synthetic demo preview and live analysis mode.
- [x] Case queue, policy library and audit activity screens.
- [ ] Add chart filtering and drill-through tied to historical saved analysis runs.
- [ ] Replace demo-only map/region/watchlist visuals with actual authorized source-backed data when available.

## Milestone 7 — Bank production readiness
- [ ] Approved infrastructure, network segmentation, TLS enforcement, secrets manager and key rotation.
- [ ] Encryption and retention controls, tested backups, tamper-evident audit storage and incident response.
- [ ] Async/background jobs, monitoring, rate limits, resource quotas and disaster recovery.
- [ ] Independent threat model, penetration test, dependency scanning and secure code review.
- [ ] Institution-specific rule calibration, model validation, legal/compliance approval and controlled pilot.

## Definition of done

- Automated tests and local setup instructions pass and match actual behavior.
- No secrets or real customer data are committed.
- Every alert is explainable and traceable to source references and a rule version.
- AI reports distinguish observed facts, retrieved sources, uncertainty and follow-up questions.
- Policy citations point to actual indexed content; external model use remains opt-in and governed.
- No consequential account or regulatory action occurs without authorized human approval.
