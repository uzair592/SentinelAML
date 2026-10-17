# AML Rule Catalogue (Prototype)

## Important interpretation

Rules below are **engineering heuristics for a demo and analyst triage**, not regulator-prescribed values and not evidence of criminality. Defaults are illustrative, must be configurable, and must not be advertised as SBP-defined thresholds. Production thresholds require institution-specific typologies, product context, calibration, validation, governance, and approval.

Every generated alert must contain: rule key, rule version, severity, concise title, why it triggered, measured values, configured parameters, evidence row references, calculation window, and limitations.

## Initial rules

| Rule key | Purpose | Example default | Evidence | Key caveat |
| --- | --- | --- | --- | --- |
| `HIGH_VALUE` | Flag an individual transaction at or above a configured amount | 1,000,000 in source currency | Transaction row and amount | Currency and product context matter |
| `VELOCITY_SPIKE` | Find an account with many transactions in a rolling time window | 10 transactions / 60 minutes | Rows in the window, count and timestamps | Busy legitimate merchants may be high volume |
| `POSSIBLE_STRUCTURING` | Surface repeated amounts just below a configured reference threshold | At least 3 amounts between 70% and 100% of threshold within 24h | Matched rows, amounts, sum, window | Pattern alone does not indicate intent; split transactions can be legitimate |
| `ROBUST_AMOUNT_OUTLIER` | Flag unusually large values relative to an account's own history | Median + 6 × MAD, minimum sample size configurable | Account baseline, median, MAD and candidate row | MAD=0 and small samples need careful handling |
| `DUPLICATE_TRANSACTION_ID` | Identify repeated transaction references | Any duplicate non-empty ID | IDs and row references | Retries/reversals may be valid and need domain-specific interpretation |
| `INVALID_CRITICAL_FIELD` | Report rows missing/unparseable timestamp, amount or source account | Any invalid required field | Row number and validation message | Data quality is not a financial-crime alert |

## Severity semantics

- **High / Medium / Low** represent configured review priority, not probability that a customer committed a crime.
- Severity must be separated from model confidence and source data quality.
- Analysts must be able to see the threshold and the exact evidence that triggered each rule.
- No alert should automatically blacklist a customer, freeze an account, or file a report.

## Avoiding common analytical errors

- Never aggregate amounts in different currencies unless they are filtered to one currency or reliably normalized with recorded FX source, rate and timestamp.
- Specify whether negative amounts are reversals, refunds, debits or outflows before applying direction-sensitive rules.
- Use event time and time zone consistently. Document whether time windows are fixed or rolling.
- Do not label a transaction as “money laundering” on the basis of a single heuristic.
- When history is absent, state that baseline-dependent analysis was not run.
- Deduplicate only when a documented idempotency rule allows it; preserve repeated rows and report them.
- Ensure tests include legitimate edge cases and false positives, not only obvious synthetic suspicious cases.

## Validation plan

1. Unit-test threshold boundaries and missing values.
2. Build labeled synthetic examples with benign high-volume patterns.
3. Report precision, recall, false-positive rate and counts by rule when ground-truth labels exist.
4. Review results by currency, account type, channel and time period where available.
5. Record rule version, configuration, analysis timestamp and data-source identity in every exported result.
6. Require compliance-owner approval before any real-world deployment.
