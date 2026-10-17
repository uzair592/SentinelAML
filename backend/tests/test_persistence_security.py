import pytest

from app.persistence import init_db, jwt_secret


def test_production_rejects_example_admin_credentials(monkeypatch):
    monkeypatch.setenv("SENTINELAML_ENV", "production")
    monkeypatch.setenv("SENTINELAML_ADMIN_EMAIL", "sentinel.admin@example.com")
    monkeypatch.setenv("SENTINELAML_ADMIN_PASSWORD", "ChangeThis-LocalOnly-123!")
    monkeypatch.setenv("SENTINELAML_JWT_SECRET", "another-secret-value-that-is-long-but-not-random-enough")
    with pytest.raises(RuntimeError, match="non-example"):
        init_db()


def test_production_rejects_placeholder_jwt_secret(monkeypatch):
    monkeypatch.setenv("SENTINELAML_ENV", "production")
    monkeypatch.setenv("SENTINELAML_JWT_SECRET", "replace-with-a-random-secret-at-least-32-characters")
    with pytest.raises(RuntimeError, match="randomly generated"):
        jwt_secret()


def test_production_accepts_configured_random_secret(monkeypatch):
    monkeypatch.setenv("SENTINELAML_ENV", "production")
    secret = "4f9c9e8a2c5b1f6e8d3a0b7c9e2f1a6d4b8c0e7f3a5d9c1b6e2a8f0d4c7b9a1e"
    monkeypatch.setenv("SENTINELAML_JWT_SECRET", secret)
    assert jwt_secret() == secret
