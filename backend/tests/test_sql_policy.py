import pytest
from fastapi import HTTPException

from app.sql_sources import _validate_network_host


def test_loopback_allowed_in_development(monkeypatch):
    monkeypatch.setenv("SENTINELAML_ENV", "development")
    monkeypatch.setenv("SENTINELAML_ALLOWED_DB_HOSTS", "")
    assert _validate_network_host("localhost") == "localhost"


def test_remote_host_requires_explicit_allowlist(monkeypatch):
    monkeypatch.setenv("SENTINELAML_ENV", "development")
    monkeypatch.setenv("SENTINELAML_ALLOWED_DB_HOSTS", "")
    with pytest.raises(HTTPException) as error:
        _validate_network_host("database.example.test")
    assert error.value.status_code == 403


def test_allowlisted_host(monkeypatch):
    monkeypatch.setenv("SENTINELAML_ENV", "production")
    monkeypatch.setenv("SENTINELAML_ALLOWED_DB_HOSTS", "db.example.test, other.example.test")
    assert _validate_network_host("DB.EXAMPLE.TEST") == "db.example.test"


def test_link_local_metadata_ip_is_blocked(monkeypatch):
    monkeypatch.setenv("SENTINELAML_ENV", "development")
    monkeypatch.setenv("SENTINELAML_ALLOWED_DB_HOSTS", "169.254.169.254")
    with pytest.raises(HTTPException):
        _validate_network_host("169.254.169.254")
