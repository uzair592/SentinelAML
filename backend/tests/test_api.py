import json

import pytest
from fastapi.testclient import TestClient

from app.main import app

DEMO_EMAIL = "sentinel.admin@sentinelaml.local"
DEMO_PASSWORD = "ChangeThis-LocalOnly-123!"


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        login = test_client.post("/api/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
        assert login.status_code == 200, login.text
        test_client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
        yield test_client


def _sample_csv() -> bytes:
    return (
        "Transaction ID,Transaction Date,Transaction Amount,Debit Account,Currency\n"
        "T-100,2026-10-01 09:00:00,2500,A-100,PKR\n"
        "T-101,2026-10-01 09:15:00,100,A-200,PKR\n"
        "T-102,2026-10-01 10:30:00,1500000,A-300,PKR\n"
    ).encode("utf-8")


def _mapping():
    return {
        "transaction_id": "Transaction ID",
        "timestamp": "Transaction Date",
        "amount": "Transaction Amount",
        "source_account": "Debit Account",
        "currency": "Currency",
    }


def test_health_endpoint():
    with TestClient(app) as client:
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


def test_analysis_requires_authentication():
    with TestClient(app) as client:
        response = client.post(
            "/api/files/preview",
            files={"file": ("transactions.csv", _sample_csv(), "text/csv")},
        )
        assert response.status_code == 401


def test_csv_preview_and_analysis_workflow(client):
    payload = _sample_csv()
    preview = client.post(
        "/api/files/preview",
        files={"file": ("transactions.csv", payload, "text/csv")},
    )
    assert preview.status_code == 200
    assert preview.json()["row_count"] == 3
    assert preview.json()["mapping_suggestions"]["timestamp"] == "Transaction Date"

    response = client.post(
        "/api/files/analyze",
        files={"file": ("transactions.csv", payload, "text/csv")},
        data={"mapping": json.dumps(_mapping()), "options": json.dumps({"large_amount_threshold": 1000})},
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["summary"]["analyzed_transactions"] == 3
    assert result["summary"]["alert_count"] >= 1
    assert result.get("analysis_run_id")
    assert any(alert["rule_id"] == "HIGH_VALUE" for alert in result["alerts"])


def test_create_persist_and_investigate_case(client):
    analysis = client.post(
        "/api/files/analyze",
        files={"file": ("transactions.csv", _sample_csv(), "text/csv")},
        data={"mapping": json.dumps(_mapping()), "options": json.dumps({"large_amount_threshold": 1000})},
    )
    assert analysis.status_code == 200, analysis.text
    result = analysis.json()
    alert = next(item for item in result["alerts"] if item["rule_id"] == "HIGH_VALUE")
    created = client.post("/api/cases", json={
        "analysis_run_id": result["analysis_run_id"],
        "alert_id": alert["alert_id"],
        "analyst_notes": "Initial synthetic-data review",
    })
    assert created.status_code == 200, created.text
    case = created.json()
    assert case["case_reference"].startswith("SAML-")
    assert case["status"] == "open"

    investigation = client.post(f"/api/cases/{case['id']}/investigate", json={"question": "Which checks should be completed?"})
    assert investigation.status_code == 200, investigation.text
    workflow = investigation.json()["workflow"]
    assert len(workflow["agents"]) == 4
    assert workflow["status"] == "draft_ready_for_human_review"
    assert workflow["report"]["human_review_required"] is True
    assert "intent or criminality" in workflow["report"]["summary"] or workflow["report"]["limitations"]

    detail = client.get(f"/api/cases/{case['id']}")
    assert detail.status_code == 200
    assert detail.json()["investigation_report"] is not None
    assert any(event["event_type"] == "case.investigation_generated" for event in detail.json()["events"])


def test_policy_upload_search_and_audit(client):
    text = (
        "Customer Due Diligence and Suspicious Transaction Monitoring. "
        "Financial institutions should identify unusual transaction patterns, review customer context, "
        "document the evidence and escalate concerns according to approved internal procedures. "
        "This is synthetic test policy content and is not legal guidance."
    )
    upload = client.post(
        "/api/policies/upload",
        files={"file": ("synthetic-policy.txt", text.encode("utf-8"), "text/plain")},
    )
    assert upload.status_code == 200, upload.text
    assert upload.json()["chunk_count"] >= 1

    search = client.post("/api/policies/search", json={"query": "suspicious transaction monitoring", "limit": 5})
    assert search.status_code == 200
    assert search.json()["results"]
    assert "synthetic test policy" in search.json()["results"][0]["content"]

    audit = client.get("/api/audit")
    assert audit.status_code == 200
    assert any(item["action"] == "policy.uploaded" for item in audit.json()["events"])
