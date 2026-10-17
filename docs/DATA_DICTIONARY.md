# Canonical Transaction Data Dictionary

Column names from imported datasets can differ. The user maps source names to these canonical names before the engine runs.

| Canonical field | Required | Logical type | Notes |
| --- | --- | --- | --- |
| `transaction_id` | No | string | Reference from source; preserve leading zeros |
| `timestamp` | Yes | datetime | Event/posting date and time with timezone interpretation documented |
| `amount` | Yes | decimal/numeric | Amount in the row's currency; do not silently coerce invalid values |
| `source_account` | Yes | string | Originator/debit account; preserve leading zeros |
| `destination_account` | No | string | Recipient/beneficiary account |
| `customer_id` | No | string | Customer reference; minimize exposure |
| `currency` | No | ISO-like currency code/string | If missing, totals must be labeled as unspecified, not assumed to be PKR |
| `transaction_type` | No | string | Transfer, cash, card, fee, reversal etc. based on source semantics |
| `channel` | No | string | Branch, mobile, ATM, agent, internet etc. if available |
| `status` | No | string | Posted, pending, reversed etc. |
| `country` | No | string | Origin/destination geography only when legitimately available |
| `balance_after` | No | decimal/numeric | Optional source balance; data-quality validation required |

## Row identity and evidence

- Source row numbers are one-based spreadsheet/CSV records (excluding the header) and should travel with alerts.
- Database sources should use a stable primary key if available. For unordered tables, do not imply a stable row order; show source key and query/import time.
- Row numbers can change between file versions, so evidence exports should include source fingerprint/import reference and original transaction ID when provided.
- Keep display identifiers separate from internal random IDs.
