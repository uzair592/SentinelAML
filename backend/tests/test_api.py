import json

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_csv_preview_and_analysis_workflow():
    payload = (
        "Transaction ID,Transaction Date,Transaction Amount,Debit Account,Currency\n"
        "T-100,2026-10-01 09:00:00,2500,A-100,PKR\n"
        "T-101,2026-10-01 09:15:00,100,A-200,PKR\n"
    ).encode("utf-8")
    preview = client.post(
        "/api/files/preview",
        files={"file": ("transactions.csv", payload, "text/csv")},
    )
    assert preview.status_code == 200
    assert preview.json()["row_count"] == 2
    assert preview.json()["mapping_suggestions"]["timestamp"] == "Transaction Date"

    mapping = {
        "transaction_id": "Transaction ID",
        "timestamp": "Transaction Date",
        "amount": "Transaction Amount",
        "source_account": "Debit Account",
        "currency": "Currency",
    }
    response = client.post(
        "/api/files/analyze",
        files={"file": ("transactions.csv", payload, "text/csv")},
        data={"mapping": json.dumps(mapping), "options": json.dumps({"large_amount_threshold": 1000})},
    )
    assert response.status_code == 200
    result = response.json()
    assert result["summary"]["analyzed_transactions"] == 2
    assert result["summary"]["alert_count"] >= 1
    assert any(alert["rule_id"] == "HIGH_VALUE" for alert in result["alerts"])
