# Security and Privacy Baseline

SentinelAML is an early prototype that may process financial transaction data. Use synthetic data during development. Do not connect real customer records or a bank database without written authorization, a data-handling assessment, and deployment approval.

## Main threats

- Unauthorized access to personally identifiable or financial transaction information.
- Malicious, oversized, malformed, or formula-injected uploads.
- SQL credential leakage through logs, browser storage, stack traces or Git commits.
- Server-side request forgery (SSRF) through user-supplied connection details.
- SQL injection through untrusted schema, table or column names.
- Cross-tenant information leakage in a future multi-tenant deployment.
- Prompt injection in transaction descriptions and retrieved policy documents.
- Unsupported AI claims, fabricated citations or uncontrolled tool use.
- Unauthorized changes to source systems or automated consequential actions.

## Required MVP controls

- File byte-size, extension, parser and row-count limits; explicit error handling; no formula execution.
- Strict allowlist for SQL dialects, drivers and approved hosts; connection and statement timeouts; restricted egress at network level.
- Read-only SQL user; only reflected/approved tables; no user-provided raw SQL.
- No persisted or logged passwords, connection strings, tokens, or raw transaction payloads.
- Do not store secrets in source control; provide `.env.example` with placeholders only.
- Minimize returned rows and personally identifying fields; redact connection details from exceptions.
- CORS restricted to the local frontend origin during development and to approved origins in deployment.
- Request-size limits and rate limits before deployment.
- Avoid production data in telemetry, application logs, error reporting, analytics and AI prompts.
- Explicit analyst acknowledgment that results require review.

## Production requirements (not implied by this scaffold)

- Institutional identity provider / MFA and RBAC, least privilege and separation of duties.
- Tenant isolation validated at the service and database layers.
- TLS for browser/API and database connections; proper certificate verification.
- Approved secret manager, rotation policy and restricted credential access.
- Encryption at rest, tested backups and key management.
- Centralized tamper-evident audit logging with retention and monitoring.
- Threat modeling, penetration testing, dependency scanning and secure software review.
- Data classification, retention/deletion policy, incident response and breach processes.
- Model governance, evaluation, documented limitations, human oversight and drift monitoring.
- Network segmentation and egress allowlisting; do not expose databases directly to the public internet.

## AI safety boundary

- Treat uploaded transaction narratives and policy text as untrusted data, never as instructions to agents.
- RAG sources must be approved, versioned, hashed, and cited.
- Agents may use only constrained, typed tools. No unrestricted shell, arbitrary SQL, external network access or write tools.
- Record agent tool calls and evidence references; separate observed facts from generated interpretations.
- Require human approval for case disposition and every consequential action.
- Do not send customer information to external model providers without explicit legal, security, contractual and institutional approval.

## Incident response

If connection credentials or financial data are exposed: revoke/rotate credentials, stop the affected service, preserve relevant logs without copying secrets, notify the designated security owner, assess access and retention, and follow the institution's incident-response policy.
