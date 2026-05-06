"""Tests for the public vendor landing page (Track C1)."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_cafe_el_tiempo_returns_branded_page() -> None:
    response = client.get("/v/cafe-el-tiempo")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")

    body = response.text
    assert "Café El Tiempo" in body
    assert "Bre-B" in body
    assert "Bogotá" in body
    assert "Cómo pagar desde el exterior" in body
    assert "Bancolombia" in body
    assert "Nequi" in body
    assert "Daviplata" in body
    assert '<svg' in body and 'viewBox="0 0 21 21"' in body


def test_unknown_vendor_returns_404() -> None:
    response = client.get("/v/unknown-vendor")
    assert response.status_code == 404


def test_html_lang_is_spanish() -> None:
    response = client.get("/v/cafe-el-tiempo")
    assert response.status_code == 200
    assert '<html lang="es">' in response.text
