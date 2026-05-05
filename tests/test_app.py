"""Light integration tests against the FastAPI app (no Kapso / network calls)."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root_returns_service_info() -> None:
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data.get("service")
    assert data.get("docs") == "/docs"


def test_health_returns_healthy() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "environment" in data
