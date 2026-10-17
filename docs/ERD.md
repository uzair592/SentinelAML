# SentinelAML Entity Relationship Diagram (ERD)

The following ERD is the **target persistent model** for case-management phases. The first file-analysis MVP may return results in memory and therefore does not require every table to exist yet. Do not store raw source credentials in this schema.

```mermaid
erDiagram
    ORGANIZATION ||--o{ APP_USER : has
    ORGANIZATION ||--o{ DATA_SOURCE : configures
    ORGANIZATION ||--o{ DATASET_IMPORT : owns
    APP_USER ||--o{ DATASET_IMPORT : initiates
    DATA_SOURCE ||--o{ DATASET_IMPORT : supplies
    DATASET_IMPORT ||--o{ SOURCE_COLUMN_MAPPING : maps
    DATASET_IMPORT ||--o{ ANALYSIS_RUN : analyzed_in
    APP_USER ||--o{ ANALYSIS_RUN : starts
    ANALYSIS_RUN ||--o{ AML_ALERT : produces
    AML_RULE ||--o{ AML_ALERT : triggers
    AML_ALERT ||--o{ ALERT_EVIDENCE : supported_by
    ANALYSIS_RUN ||--o{ DATA_QUALITY_FINDING : reports
    AML_ALERT ||--o| INVESTIGATION_CASE : may_open
    APP_USER ||--o{ INVESTIGATION_CASE : assigned_to
    INVESTIGATION_CASE ||--o{ CASE_NOTE : contains
    INVESTIGATION_CASE ||--o{ CASE_EVENT : records
    APP_USER ||--o{ CASE_NOTE : writes
    APP_USER ||--o{ AUDIT_EVENT : performs
    ORGANIZATION ||--o{ AUDIT_EVENT : scopes
    POLICY_DOCUMENT ||--o{ POLICY_CHUNK : contains

    ORGANIZATION {
        uuid id PK
        string name
        string status
        datetime created_at
    }
    APP_USER {
        uuid id PK
        uuid organization_id FK
        string email
        string display_name
        string role
        string status
        datetime created_at
    }
    DATA_SOURCE {
        uuid id PK
        uuid organization_id FK
        string name
        string source_type
        string host_reference
        string database_name
        string schema_name
        string status
        datetime created_at
    }
    DATASET_IMPORT {
        uuid id PK
        uuid organization_id FK
        uuid source_id FK
        uuid initiated_by FK
        string source_kind
        string original_filename
        string source_table
        int row_count
        string status
        datetime created_at
    }
    SOURCE_COLUMN_MAPPING {
        uuid id PK
        uuid dataset_import_id FK
        string canonical_field
        string source_column
        float confidence
    }
    ANALYSIS_RUN {
        uuid id PK
        uuid dataset_import_id FK
        uuid started_by FK
        string engine_version
        json options
        int rows_analyzed
        string status
        datetime started_at
        datetime completed_at
    }
    AML_RULE {
        uuid id PK
        string rule_key
        string version
        string description
        string severity
        json default_parameters
        boolean enabled
    }
    AML_ALERT {
        uuid id PK
        uuid analysis_run_id FK
        uuid rule_id FK
        string severity
        string status
        string subject_reference
        string title
        string explanation
        json calculated_values
        datetime created_at
    }
    ALERT_EVIDENCE {
        uuid id PK
        uuid alert_id FK
        int source_row_number
        string transaction_reference
        json evidence
    }
    DATA_QUALITY_FINDING {
        uuid id PK
        uuid analysis_run_id FK
        string finding_key
        string severity
        string message
        int affected_rows
        json examples
    }
    INVESTIGATION_CASE {
        uuid id PK
        uuid alert_id FK
        uuid assigned_to FK
        string case_reference
        string status
        string disposition
        string summary
        datetime opened_at
        datetime closed_at
    }
    CASE_NOTE {
        uuid id PK
        uuid investigation_case_id FK
        uuid author_id FK
        string note
        datetime created_at
    }
    CASE_EVENT {
        uuid id PK
        uuid investigation_case_id FK
        string event_type
        json event_payload
        datetime created_at
    }
    AUDIT_EVENT {
        uuid id PK
        uuid organization_id FK
        uuid actor_id FK
        string action
        string resource_type
        string resource_id
        json metadata
        datetime created_at
    }
    POLICY_DOCUMENT {
        uuid id PK
        string title
        string source_url
        string version_label
        string document_hash
        datetime ingested_at
    }
    POLICY_CHUNK {
        uuid id PK
        uuid policy_document_id FK
        int chunk_index
        string content
        vector embedding
        json source_metadata
    }
```

## Entity notes and constraints

- `organization_id` belongs on every tenant-owned record; production queries must scope by the authenticated tenant.
- Database passwords, full secret-bearing connection URLs, access tokens, and raw private keys must never be persisted in `DATA_SOURCE`.
- `host_reference` should identify an administrator-approved host entry, not be a free-form secret connection string.
- Evidence should be minimized and protected. Prefer stable source-row references plus selected fields rather than copying complete financial records into every alert.
- Store each analysis rule's version and parameters with the run so reviewers can reproduce why an alert was generated.
- Use foreign keys, indexes on time/status/organization, unique constraints for rule keys and source mappings, and soft-delete/retention policy where appropriate.
- The `vector` type in the diagram is conceptual; implementation may use pgvector or a separate approved retrieval service.
