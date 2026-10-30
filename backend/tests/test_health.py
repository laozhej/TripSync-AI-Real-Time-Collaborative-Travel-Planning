import pytest
from fastapi.testclient import TestClient
from app.main import app


def test_live_without_database_connection(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://invalid:invalid@127.0.0.1:1/invalid")
    with TestClient(app) as client:
        assert client.get("/api/v1/health/live").json() == {"status": "ok"}
        response = client.get("/api/v1/health/ready")
        assert response.status_code == 503
        assert "invalid" not in response.text


def test_missing_database_configuration_fails_closed(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        with TestClient(app):
            pass
