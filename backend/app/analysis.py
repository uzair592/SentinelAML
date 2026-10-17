"""Explainable deterministic analysis. Alerts identify review-worthy patterns, not criminality."""
from __future__ import annotations

from collections import Counter, defaultdict, deque
from datetime import timedelta
from typing import Any
import math

import numpy as np
import pandas as pd

CANONICAL_FIELDS = {
    "transaction_id", "timestamp", "amount", "source_account",
    "destination_account", "customer_id", "currency", "transaction_type",
    "channel", "status", "country", "balance_after",
}
REQUIRED_FIELDS = ("timestamp", "amount", "source_account")
DEFAULT_OPTIONS: dict[str, Any] = {
    "large_amount_threshold": 1_000_000,
    "velocity_count_threshold": 10,
    "velocity_window_minutes": 60,
    "structuring_reference_threshold": 1_000_000,
    "structuring_min_transactions": 3,
    "structuring_window_hours": 24,
    "outlier_mad_multiplier": 6,
    "outlier_min_transactions": 8,
}
MAX_ALERTS = 2_000


def validate_mapping(columns: list[str], mapping: dict[str, str | None]) -> dict[str, str | None]:
    unknown_fields = sorted(set(mapping) - CANONICAL_FIELDS)
    if unknown_fields:
        raise ValueError(f"Unsupported canonical fields: {', '.join(unknown_fields)}")
    cleaned: dict[str, str | None] = {}
    for field in CANONICAL_FIELDS:
        source = mapping.get(field)
        if source in (None, ""):
            cleaned[field] = None
            continue
        if not isinstance(source, str) or source not in columns:
            raise ValueError(f"The selected source column for {field} does not exist.")
        cleaned[field] = source
    missing = [field for field in REQUIRED_FIELDS if not cleaned.get(field)]
    if missing:
        raise ValueError("Map these required fields before analysis: " + ", ".join(missing))
    selected = [value for value in cleaned.values() if value]
    if len(selected) != len(set(selected)):
        raise ValueError("A source column cannot be mapped to more than one canonical field.")
    return cleaned


def _to_float(value: Any, default: float) -> float:
    try:
        result = float(value)
        return result if math.isfinite(result) and result > 0 else default
    except (TypeError, ValueError):
        return default


def _positive_int(value: Any, default: int, upper: int = 1_000_000) -> int:
    try:
        result = int(value)
        return min(max(result, 1), upper)
    except (TypeError, ValueError):
        return default


def _json_num(value: Any) -> float | None:
    try:
        number = float(value)
        return round(number, 4) if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _canonicalize(frame: pd.DataFrame, mapping: dict[str, str | None]) -> tuple[pd.DataFrame, dict[str, int], list[dict[str, Any]]]:
    mapping = validate_mapping([str(c) for c in frame.columns], mapping)
    out = pd.DataFrame(index=frame.index)
    for field, source in mapping.items():
        if source:
            out[field] = frame[source].astype(str).str.strip()
        else:
            out[field] = ""
    out["source_row_number"] = np.arange(2, len(frame) + 2, dtype=int)
    out["_original_index"] = np.arange(len(frame), dtype=int)
    original_time = out["timestamp"].copy()
    original_amount = out["amount"].copy()
    out["timestamp"] = pd.to_datetime(out["timestamp"], errors="coerce", utc=True, format="mixed")
    out["amount"] = pd.to_numeric(out["amount"].str.replace(",", "", regex=False).str.replace(r"^[^0-9+\-\.]", "", regex=True), errors="coerce")
    out["source_account"] = out["source_account"].replace("", pd.NA)
    # Empty optional identifiers stay empty strings for stable JSON output.
    for col in ("destination_account", "customer_id", "transaction_id", "currency", "transaction_type", "channel", "status", "country"):
        out[col] = out[col].fillna("").astype(str).str.strip()
    out["currency"] = out["currency"].replace("", "UNSPECIFIED").str.upper()
    invalid_time = int(out["timestamp"].isna().sum())
    invalid_amount = int(out["amount"].isna().sum())
    invalid_source = int(out["source_account"].isna().sum())
    valid = out["timestamp"].notna() & out["amount"].notna() & out["source_account"].notna()
    quality: list[dict[str, Any]] = []
    quality_checks = [
        ("INVALID_TIMESTAMP", invalid_time, "Rows with missing or unparseable timestamps.", out["timestamp"].isna()),
        ("INVALID_AMOUNT", invalid_amount, "Rows with missing or non-numeric transaction amounts.", out["amount"].isna()),
        ("MISSING_SOURCE_ACCOUNT", invalid_source, "Rows with a missing source account identifier.", out["source_account"].isna()),
    ]
    for key, count, message, condition in quality_checks:
        if count:
            examples = out.loc[condition, "source_row_number"].head(20).astype(int).tolist()
            quality.append({"finding_key": key, "severity": "medium", "message": message, "affected_rows": count, "example_row_numbers": examples})
    out["_valid"] = valid
    # Keep originals for a safe quality example without leaking full records.
    out["_original_timestamp"] = original_time
    out["_original_amount"] = original_amount
    return out, {"invalid_timestamp": invalid_time, "invalid_amount": invalid_amount, "missing_source_account": invalid_source}, quality


def _alert(rule: str, severity: str, title: str, explanation: str, evidence: list[int], values: dict[str, Any], subject: str | None = None) -> dict[str, Any]:
    row_token = evidence[0] if evidence else 0
    return {
        "alert_id": f"ALR-{rule}-{row_token}",
        "rule_id": rule,
        "rule_version": "1.0.0",
        "severity": severity,
        "status": "needs_review",
        "title": title,
        "explanation": explanation,
        "subject_reference": subject,
        "evidence_row_numbers": sorted({int(x) for x in evidence})[:100],
        "evidence_count": len(set(evidence)),
        "measured_values": values,
        "interpretation": "This is a review indicator generated by a configured heuristic, not a finding of criminality.",
    }


def _best_window(group: pd.DataFrame, time_column: str, window: pd.Timedelta, predicate=None) -> list[int]:
    records = group.sort_values(time_column)
    if predicate is not None:
        records = records.loc[predicate(records)]
    if records.empty:
        return []
    times = records[time_column].tolist()
    rows = records["source_row_number"].astype(int).tolist()
    left = 0
    best_left, best_right = 0, 0
    for right in range(len(records)):
        while left <= right and times[right] - times[left] > window:
            left += 1
        if right - left > best_right - best_left:
            best_left, best_right = left, right
    return rows[best_left:best_right + 1] if best_right >= best_left else []


def analyze_dataframe(frame: pd.DataFrame, mapping: dict[str, str | None], options: dict[str, Any] | None = None, source: dict[str, Any] | None = None) -> dict[str, Any]:
    settings = {**DEFAULT_OPTIONS, **(options or {})}
    large_threshold = _to_float(settings.get("large_amount_threshold"), DEFAULT_OPTIONS["large_amount_threshold"])
    structuring_threshold = _to_float(settings.get("structuring_reference_threshold"), DEFAULT_OPTIONS["structuring_reference_threshold"])
    velocity_count = _positive_int(settings.get("velocity_count_threshold"), DEFAULT_OPTIONS["velocity_count_threshold"], 100_000)
    velocity_minutes = _positive_int(settings.get("velocity_window_minutes"), DEFAULT_OPTIONS["velocity_window_minutes"], 10_080)
    structuring_min = _positive_int(settings.get("structuring_min_transactions"), DEFAULT_OPTIONS["structuring_min_transactions"], 100_000)
    structuring_hours = _positive_int(settings.get("structuring_window_hours"), DEFAULT_OPTIONS["structuring_window_hours"], 8_760)
    outlier_multiplier = _to_float(settings.get("outlier_mad_multiplier"), DEFAULT_OPTIONS["outlier_mad_multiplier"])
    outlier_min = _positive_int(settings.get("outlier_min_transactions"), DEFAULT_OPTIONS["outlier_min_transactions"], 100_000)

    canonical, invalid_counts, quality = _canonicalize(frame, mapping)
    valid = canonical.loc[canonical["_valid"]].copy()
    alerts: list[dict[str, Any]] = []
    capped = False

    if valid.empty:
        return {
            "source": source or {},
            "summary": {"total_transactions": int(len(frame)), "analyzed_transactions": 0, "excluded_transactions": int(len(frame)), "date_range": None, "unique_source_accounts": 0, "unique_destination_accounts": 0, "unique_customers": 0, "alert_count": 0, "alerts_by_severity": {"high": 0, "medium": 0, "low": 0}},
            "totals_by_currency": [],
            "data_quality": quality,
            "alerts": [],
            "rule_counts": {},
            "options_used": {"large_amount_threshold": large_threshold, "velocity_count_threshold": velocity_count, "velocity_window_minutes": velocity_minutes, "structuring_reference_threshold": structuring_threshold, "structuring_min_transactions": structuring_min, "structuring_window_hours": structuring_hours, "outlier_mad_multiplier": outlier_multiplier, "outlier_min_transactions": outlier_min},
            "warnings": ["No rows passed required timestamp, amount, and source-account validation."],
        }

    # Monetary summaries remain split by currency.
    totals = []
    for currency, group in valid.groupby("currency", dropna=False):
        amounts = group["amount"].astype(float)
        totals.append({
            "currency": str(currency),
            "transaction_count": int(len(group)),
            "total_amount": _json_num(amounts.sum()),
            "average_amount": _json_num(amounts.mean()),
            "median_amount": _json_num(amounts.median()),
            "maximum_amount": _json_num(amounts.max()),
        })
    totals.sort(key=lambda item: item["currency"])

    # High-value single transaction.
    high = valid.loc[valid["amount"] >= large_threshold]
    for _, row in high.head(MAX_ALERTS).iterrows():
        alerts.append(_alert(
            "HIGH_VALUE", "high", "Transaction exceeds configured amount threshold",
            f"Transaction amount {row['amount']:,.2f} {row['currency']} meets or exceeds the configured review threshold {large_threshold:,.2f}.",
            [int(row["source_row_number"])],
            {"amount": _json_num(row["amount"]), "currency": row["currency"], "threshold": large_threshold, "timestamp": row["timestamp"].isoformat()},
            str(row["source_account"]),
        ))
    if len(high) > MAX_ALERTS:
        capped = True

    # Transaction velocity: one alert per account for its densest qualifying rolling window.
    window = pd.Timedelta(minutes=velocity_minutes)
    for account, group in valid.groupby("source_account", sort=False):
        ordered = group.sort_values("timestamp")
        if len(ordered) < velocity_count:
            continue
        times = ordered["timestamp"].tolist()
        rows = ordered["source_row_number"].astype(int).tolist()
        left = 0
        best = (0, -1)
        for right in range(len(ordered)):
            while left <= right and times[right] - times[left] > window:
                left += 1
            if right - left + 1 > best[1] - best[0] + 1:
                best = (left, right)
        count = best[1] - best[0] + 1
        if count >= velocity_count:
            evidence = rows[best[0]:best[1] + 1]
            alerts.append(_alert("VELOCITY_SPIKE", "medium", "High transaction frequency for account",
                f"{count} transactions occurred within {velocity_minutes} minutes for this source account, meeting the configured count threshold {velocity_count}.",
                evidence, {"transaction_count": count, "window_minutes": velocity_minutes, "threshold_count": velocity_count}, str(account)))

    # Possible structuring: multiple near-threshold amounts in a defined time window.
    near_low = 0.70 * structuring_threshold
    candidates = valid.loc[(valid["amount"] >= near_low) & (valid["amount"] < structuring_threshold)]
    struct_window = pd.Timedelta(hours=structuring_hours)
    for account, group in candidates.groupby("source_account", sort=False):
        ordered = group.sort_values("timestamp")
        if len(ordered) < structuring_min:
            continue
        times = ordered["timestamp"].tolist()
        amounts = ordered["amount"].astype(float).tolist()
        rows = ordered["source_row_number"].astype(int).tolist()
        left = 0
        best = (0, -1)
        for right in range(len(ordered)):
            while left <= right and times[right] - times[left] > struct_window:
                left += 1
            if right - left + 1 > best[1] - best[0] + 1:
                best = (left, right)
        count = best[1] - best[0] + 1
        if count >= structuring_min:
            evidence = rows[best[0]:best[1] + 1]
            amount_sum = sum(amounts[best[0]:best[1] + 1])
            alerts.append(_alert("POSSIBLE_STRUCTURING", "high", "Repeated transactions near the configured reference threshold",
                f"{count} transactions for this source account fell between 70% and 100% of the configured reference threshold within {structuring_hours} hours. This pattern needs context and does not establish intent.",
                evidence, {"transaction_count": count, "sum_of_amounts": _json_num(amount_sum), "lower_bound": _json_num(near_low), "upper_bound_exclusive": structuring_threshold, "window_hours": structuring_hours}, str(account)))

    # Account-specific robust outlier rule; skip baselines with too few samples or no variation.
    for account, group in valid.groupby("source_account", sort=False):
        amounts = group["amount"].astype(float)
        if len(group) < outlier_min:
            continue
        median = float(amounts.median())
        mad = float((amounts - median).abs().median())
        if not math.isfinite(mad) or mad <= 0:
            continue
        limit = median + outlier_multiplier * 1.4826 * mad
        outliers = group.loc[group["amount"].astype(float) > limit]
        for _, row in outliers.head(max(0, MAX_ALERTS - len(alerts))).iterrows():
            alerts.append(_alert("ROBUST_AMOUNT_OUTLIER", "medium", "Amount is unusual relative to this account's observed history",
                f"The amount exceeds the account median plus {outlier_multiplier:g} × 1.4826 × median absolute deviation. This comparison is only meaningful if the imported history is representative.",
                [int(row["source_row_number"])],
                {"amount": _json_num(row["amount"]), "account_median": _json_num(median), "median_absolute_deviation": _json_num(mad), "configured_multiplier": outlier_multiplier, "computed_limit": _json_num(limit)},
                str(account)))

    # Duplicate transaction IDs are data-integrity signals, not proof of duplicated payments.
    ids = valid.loc[valid["transaction_id"].ne("")]
    duplicate_ids = ids.loc[ids["transaction_id"].duplicated(keep=False)]
    for txn_id, group in duplicate_ids.groupby("transaction_id", sort=False):
        evidence = group["source_row_number"].astype(int).tolist()
        alerts.append(_alert("DUPLICATE_TRANSACTION_ID", "low", "Transaction reference appears more than once",
            "The same non-empty transaction identifier appears in multiple imported rows. Check retries, reversals, and source-system semantics before treating records as duplicates.",
            evidence, {"transaction_id": str(txn_id), "row_count": len(group)}, str(group.iloc[0]["source_account"])))
        if len(alerts) >= MAX_ALERTS:
            capped = True
            break

    # Summary quality indicators.
    if invalid_counts["invalid_timestamp"] or invalid_counts["invalid_amount"] or invalid_counts["missing_source_account"]:
        quality.append({
            "finding_key": "ROWS_EXCLUDED_FROM_ANALYSIS",
            "severity": "medium",
            "message": "Rows missing a valid required timestamp, amount, or source account were excluded from transaction rules.",
            "affected_rows": int((~canonical["_valid"]).sum()),
            "example_row_numbers": canonical.loc[~canonical["_valid"], "source_row_number"].head(20).astype(int).tolist(),
        })
    negative_count = int((valid["amount"] < 0).sum())
    zero_count = int((valid["amount"] == 0).sum())
    if negative_count or zero_count:
        quality.append({
            "finding_key": "ZERO_OR_NEGATIVE_AMOUNTS",
            "severity": "low",
            "message": "Zero and/or negative amounts exist. Confirm whether these represent fees, reversals, refunds, or another source-specific meaning.",
            "affected_rows": negative_count + zero_count,
            "example_row_numbers": valid.loc[valid["amount"] <= 0, "source_row_number"].head(20).astype(int).tolist(),
        })

    alerts.sort(key=lambda a: ({"high": 0, "medium": 1, "low": 2}.get(a["severity"], 3), a["rule_id"], a["alert_id"]))
    if len(alerts) > MAX_ALERTS:
        alerts = alerts[:MAX_ALERTS]
        capped = True
    severity_counts = Counter(alert["severity"] for alert in alerts)
    rule_counts: dict[str, int] = dict(Counter(alert["rule_id"] for alert in alerts))
    min_date = valid["timestamp"].min()
    max_date = valid["timestamp"].max()
    summary = {
        "total_transactions": int(len(frame)),
        "analyzed_transactions": int(len(valid)),
        "excluded_transactions": int((~canonical["_valid"]).sum()),
        "date_range": {"start": min_date.isoformat(), "end": max_date.isoformat()},
        "unique_source_accounts": int(valid["source_account"].nunique()),
        "unique_destination_accounts": int(valid.loc[valid["destination_account"].ne(""), "destination_account"].nunique()),
        "unique_customers": int(valid.loc[valid["customer_id"].ne(""), "customer_id"].nunique()),
        "alert_count": int(len(alerts)),
        "alerts_by_severity": {"high": severity_counts.get("high", 0), "medium": severity_counts.get("medium", 0), "low": severity_counts.get("low", 0)},
    }
    warnings: list[str] = []
    if valid["currency"].nunique() > 1:
        warnings.append("Amounts are summarized separately by currency; no cross-currency total is calculated.")
    if (valid["currency"] == "UNSPECIFIED").any():
        warnings.append("Some transactions have no mapped currency. Their totals are labeled UNSPECIFIED and must not be assumed to be PKR.")
    if source and source.get("truncated"):
        warnings.append("The source was truncated to the configured row limit; later records were not analyzed.")
    if capped:
        warnings.append(f"Alert output was capped at {MAX_ALERTS} items. Consider narrower date filters or a larger approved analysis worker.")
    warnings.append("Configured thresholds are demonstration heuristics, not regulatory thresholds. Review evidence before any action.")
    return {
        "source": source or {},
        "summary": summary,
        "totals_by_currency": totals,
        "data_quality": quality,
        "alerts": alerts,
        "rule_counts": rule_counts,
        "options_used": {
            "large_amount_threshold": large_threshold,
            "velocity_count_threshold": velocity_count,
            "velocity_window_minutes": velocity_minutes,
            "structuring_reference_threshold": structuring_threshold,
            "structuring_min_transactions": structuring_min,
            "structuring_window_hours": structuring_hours,
            "outlier_mad_multiplier": outlier_multiplier,
            "outlier_min_transactions": outlier_min,
        },
        "warnings": warnings,
    }
