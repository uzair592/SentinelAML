import pandas as pd
import pytest

from app.analysis import analyze_dataframe, validate_mapping


def base_rows():
    return pd.DataFrame([
        {"Txn ID": "T-1", "Date": "2026-10-01 09:00:00", "Value": "200", "Debit Account": "A1", "Currency": "PKR"},
        {"Txn ID": "T-2", "Date": "2026-10-01 09:15:00", "Value": "300", "Debit Account": "A1", "Currency": "PKR"},
        {"Txn ID": "T-3", "Date": "2026-10-01 09:30:00", "Value": "1500000", "Debit Account": "A2", "Currency": "PKR"},
        {"Txn ID": "T-4", "Date": "2026-10-01 10:00:00", "Value": "100", "Debit Account": "A3", "Currency": "USD"},
        {"Txn ID": "T-4", "Date": "2026-10-01 10:01:00", "Value": "100", "Debit Account": "A3", "Currency": "USD"},
    ])


def mapping():
    return {"transaction_id": "Txn ID", "timestamp": "Date", "amount": "Value", "source_account": "Debit Account", "currency": "Currency"}


def test_required_mapping_validation():
    with pytest.raises(ValueError, match="timestamp"):
        validate_mapping(list(base_rows().columns), {"amount": "Value", "source_account": "Debit Account"})


def test_high_value_rule_links_source_row():
    result = analyze_dataframe(base_rows(), mapping(), {"large_amount_threshold": 1_000_000})
    high = [alert for alert in result["alerts"] if alert["rule_id"] == "HIGH_VALUE"]
    assert len(high) == 1
    assert high[0]["evidence_row_numbers"] == [4]
    assert high[0]["measured_values"]["currency"] == "PKR"


def test_amounts_are_not_aggregated_across_currencies():
    result = analyze_dataframe(base_rows(), mapping())
    assert {item["currency"] for item in result["totals_by_currency"]} == {"PKR", "USD"}
    assert any("separately by currency" in warning for warning in result["warnings"])


def test_duplicate_id_is_a_low_severity_review_signal():
    result = analyze_dataframe(base_rows(), mapping())
    duplicate = [alert for alert in result["alerts"] if alert["rule_id"] == "DUPLICATE_TRANSACTION_ID"]
    assert len(duplicate) == 1
    assert duplicate[0]["severity"] == "low"
    assert duplicate[0]["evidence_row_numbers"] == [5, 6]


def test_bad_amount_is_reported_not_silently_zeroed():
    data = base_rows()
    data.loc[0, "Value"] = "not-a-number"
    result = analyze_dataframe(data, mapping())
    assert result["summary"]["excluded_transactions"] == 1
    assert any(item["finding_key"] == "INVALID_AMOUNT" for item in result["data_quality"])
