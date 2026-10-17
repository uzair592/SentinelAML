import pandas as pd

from app.ingestion import infer_column_type, suggest_mapping


def test_suggest_mapping_matches_common_bank_headers():
    result = suggest_mapping(["Transaction Reference", "Posting Date", "Transaction Amount", "Debit Account", "Currency"])
    assert result["transaction_id"] == "Transaction Reference"
    assert result["timestamp"] == "Posting Date"
    assert result["amount"] == "Transaction Amount"
    assert result["source_account"] == "Debit Account"


def test_column_type_inference():
    assert infer_column_type(pd.Series(["125", "200", "300"])) == "numeric"
    assert infer_column_type(pd.Series(["2026-10-01", "2026-10-02", "2026-10-03"])) == "datetime"
    assert infer_column_type(pd.Series(["branch", "mobile", "ATM"])) == "text"
