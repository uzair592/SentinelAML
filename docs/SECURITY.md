# Security and Privacy Baseline

SentinelAML is a local-first prototype for financial transaction review. Use synthetic data during development. Do not connect real customer records or a bank database without written authorization, a data-handling assessment, and deployment approval.

## Current prototype controls

- Short-lived JWT bearer tokens protect analysis, SQL, case, policy and audit endpoints; health and login remain public.
- Passwords are stored as salted scrypt hashes. The client keeps the access token in memory and requires sign-in after refresh.
- File byte-size, extension, parser and row-count limits; input errors are constrained so parser internals and submitted values are not exposed.
- Strict SQL dialect allowlist, remote-host allowlisting, bounded reflection-based table reads, and a restricted SQLite directory opened read-only.
- Database credentials are sent request-by-request and are not intentionally persisted or returned by API responses.
- Analysis source rows are processed in memory; analysis summaries and minimized alert snapshots persist to support investigation cases.
- Policy documents and extracted searchable passages are stored in the application database.
- CSV alert exports neutralize formula-leading values.
- Optional external LLM synthesis is disabled by default and, when explicitly enabled, receives a minimized alert summary without account/customer identifiers plus retrieved policy excerpts.
- All alerts are review indicators. No automatic account freezes, transfers, or regulatory submissions are implemented.

## Development-only credentials

A fresh development database is bootstrapped from `SENTINELAML_ADMIN_EMAIL` and `SENTINELAML_ADMIN_PASSWORD`. The repository's example values are for localhost demonstrations only. Change them in `.env` and never expose the development server or default credentials to a network. Production mode refuses to start without a strong admin password and a configured JWT secret.

## Main threats

- Unauthorized access to personal or financial transaction information.
- Malicious, oversized, malformed, or formula-injected uploads.
- SQL credential leakage through logs, browser storage, stack traces or source control.
- SSRF through attacker-controlled SQL host settings.
- SQL injection through untrusted schema, table or column names.
- Cross-tenant information leakage if multi-tenancy is added without proper isolation.
- Prompt injection in uploaded policy text and unsupported AI claims.
- Unauthorized case changes, audit-log tampering, and unapproved external processing.

## Remaining controls required before bank use

- Institutional identity provider, MFA/SSO, tested RBAC, user lifecycle management and separation of duties.
- Tenant isolation validated across every request and database access path.
- TLS for browser/API and database connections with enforced certificate verification; database-specific statement timeouts.
- Approved secrets manager, key rotation, strict network segmentation and outbound allowlisting.
- Encryption at rest, key management, tested backups, retention/deletion and incident-response processes.
- Tamper-evident centralized audit storage with restricted access and monitoring. The current DB-backed audit events can be modified by a sufficiently privileged database operator.
- Rate limits, request quotas, background-job isolation, monitoring, dependency scanning, threat modeling and independent penetration testing.
- Data classification, approved retention and data-processing agreements for any external model.
- Model governance, prompt-injection tests, citation-grounding evaluations, drift monitoring, and formal human-review procedures.
- Institution-specific AML rule calibration and formal business/compliance approval before operational use.

## AI safety boundary

- Treat uploaded transaction narratives and policy text as untrusted data, not instructions.
- Policy citations must resolve to actual indexed passage identifiers; users must verify the original source and current version.
- Agents may use only bounded internal tools; no unrestricted shell, arbitrary SQL, external browsing or source-database write access.
- External model support must remain opt-in. Never send regulated/customer information to a third-party provider without legal, privacy, security and contractual approval.
- Distinguish observed facts, retrieved policy context, uncertainty and generated recommendations.
- Require authorized human approval for case disposition and every consequential operational action.

## Incident response

If credentials or financial data are exposed: revoke/rotate affected credentials, stop the affected service, preserve relevant logs without copying secrets, notify the designated security owner, assess access and retention, and follow the institution's incident-response policy.
