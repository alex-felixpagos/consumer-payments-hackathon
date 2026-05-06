"""Tests for /api/buy-ticket — happy path + card-rejected path.

Mocks Procinal HTTP at the ``httpx.AsyncClient.request`` boundary so we never
hit the real API in CI.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app


# ---- Fixtures ----------------------------------------------------------

LOGIN_OK = {
    "code": 200,
    "message": "Has iniciado sesión satisfatoriamente.",
    "user": {"id": 855873, "nombre": "Diego", "apellido": "Villafuerte"},
    "access_token": "fake.jwt.token",
    "token_type": "Bearer",
    "expires_at": "2026-11-06 10:51:20",
}

SHOWTIME_DETAIL = {
    "email": None,
    "bill": [{"Secuencia": 469485, "Recargo_Venta_Internet": 1500}],
    "prices": [
        {"codigo": 103, "valor": 6250, "zona": "GENERAL", "silla": "General",
         "descripcion": "50% Base 2D (Web)", "medioPago": 0},
    ],
    "mapRoom": {
        "FilaTotal":      ["A","A","A", "B","B","B", "C","C","C"],
        "ColumnaTotal":   [1,2,3, 1,2,3, 1,2,3],
        "FilaRelativa":   ["I","I","I", "H","H","H", "G","G","G"],
        "ColumnaRelativa":[3,2,1, 3,2,1, 3,2,1],
        "TipoSilla":      ["General","General","General",
                           "General","General","General",
                           "General","General","General"],
        "TipoZona":       ["GENERAL"]*9,
    },
    "statusRoom": [
        {"maxCol": 3, "maxFil": "I", "filRel": "I",
         "DescripcionSilla": [
             {"TipoSilla": "General", "EstadoSilla": "S", "Columna": 3},
             {"TipoSilla": "General", "EstadoSilla": "S", "Columna": 2},
             {"TipoSilla": "General", "EstadoSilla": "S", "Columna": 1},
         ]},
        {"maxCol": 3, "maxFil": "I", "filRel": "H",
         "DescripcionSilla": [
             {"TipoSilla": "General", "EstadoSilla": "S", "Columna": 3},
             {"TipoSilla": "General", "EstadoSilla": "S", "Columna": 2},
             {"TipoSilla": "General", "EstadoSilla": "S", "Columna": 1},
         ]},
        {"maxCol": 3, "maxFil": "I", "filRel": "G",
         "DescripcionSilla": [
             {"TipoSilla": "General", "EstadoSilla": "S", "Columna": 3},
             {"TipoSilla": "General", "EstadoSilla": "S", "Columna": 2},
             {"TipoSilla": "General", "EstadoSilla": "S", "Columna": 1},
         ]},
    ],
    "puntoVenta": 78,
}

RESERVE_OK = {
    "message": "Reserva exitosa",
    "data": {"id": 1149999, "user_id": 855873, "score_response": '{"code":200}'},
    "code": 200,
}

PAY_OK = {
    "code": 200,
    "message": "Pago aprobado",
    "pay": {"data": {
        "ref_payco": 364386146,
        "factura": "PRO-1778083645-831",
        "valor": 7750,
        "estado": "Aceptada",
        "respuesta": "Aprobada",
        "autorizacion": "654321",
        "descripcion": "Plaza de las Américas; EL DIABLO VISTE A LA MODA 2; ...",
        "cod_respuesta": 1,
    }},
}

PAY_REJECTED = {
    "code": 403,
    "message": "Hubo un error al procesar el pago",
    "pay": {"data": {
        "ref_payco": 364386146,
        "factura": "PRO-1778083645-831",
        "valor": 7750,
        "estado": "Rechazada",
        "respuesta": "Rechazada eControl,Tarjeta no permitida por la empresa",
        "autorizacion": "000000",
        "cod_error": "ED-024",
        "cod_respuesta": 2,
    }},
}


def _set_procinal_env(monkeypatch) -> None:
    monkeypatch.setenv("PROCINAL_DOCUMENTO", "00000000")
    monkeypatch.setenv("PROCINAL_CLAVE", "test-fixture-pw")
    monkeypatch.setenv("PROCINAL_EMAIL", "test@felixpago.com")
    monkeypatch.setenv("PROCINAL_CARD_NUMBER", "4242424242424242")
    monkeypatch.setenv("PROCINAL_CARD_EXP_MONTH", "12")
    monkeypatch.setenv("PROCINAL_CARD_EXP_YEAR", "2030")
    monkeypatch.setenv("PROCINAL_CARD_CVC", "123")
    from app.config import get_settings
    get_settings.cache_clear()
    # Also clear procinal_client's JWT cache between tests
    import app.services.procinal_client as pc
    pc._jwt_cache = None


def _mock_response(status_code: int, body: dict[str, Any]) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = json.dumps(body)
    resp.json.return_value = body
    return resp


def _make_request_router(routes: list[tuple[str, str, int, dict]]) -> AsyncMock:
    """Build an AsyncMock matching httpx requests in order.

    Each entry: (method, path_substring, status, body).
    """
    queue = list(routes)

    async def _request_impl(method, url, **kwargs):
        if not queue:
            raise AssertionError(f"unexpected request: {method} {url}")
        exp_method, path, status, body = queue.pop(0)
        assert method.upper() == exp_method.upper(), (
            f"expected {exp_method} but got {method} for {url}"
        )
        assert path in url, f"expected '{path}' in URL '{url}'"
        return _mock_response(status, body)

    mock = AsyncMock()
    mock.request = AsyncMock(side_effect=_request_impl)
    return mock


def _patch_async_client(monkeypatch, mock_client: AsyncMock) -> None:
    class _Ctx:
        def __init__(self, *a, **kw): pass
        async def __aenter__(self): return mock_client
        async def __aexit__(self, *exc): return False
    monkeypatch.setattr("app.services.procinal_client.httpx.AsyncClient", _Ctx)


# ---- Tests -------------------------------------------------------------

def test_buy_ticket_happy_path(monkeypatch) -> None:
    _set_procinal_env(monkeypatch)

    mock_client = _make_request_router([
        ("POST", "/api/auth/login",                 200, LOGIN_OK),
        ("GET",  "/api/showtimes/542060",           200, SHOWTIME_DETAIL),
        ("POST", "/api/auth/payment/reservation",   200, RESERVE_OK),
        ("POST", "/api/auth/payment/card",          200, PAY_OK),
    ])
    _patch_async_client(monkeypatch, mock_client)

    client = TestClient(app)
    resp = client.post("/api/buy-ticket", json={"showtime_id": 542060})

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["factura"] == "PRO-1778083645-831"
    assert data["estado"] == "Aceptada"
    assert data["autorizacion"] == "654321"
    assert data["total_cop"] == 7750
    assert data["seat"]  # any of A1..C3 from the mock map
    # All four expected requests consumed
    assert mock_client.request.await_count == 4


def test_buy_ticket_card_rejected(monkeypatch) -> None:
    _set_procinal_env(monkeypatch)

    mock_client = _make_request_router([
        ("POST", "/api/auth/login",                 200, LOGIN_OK),
        ("GET",  "/api/showtimes/542060",           200, SHOWTIME_DETAIL),
        ("POST", "/api/auth/payment/reservation",   200, RESERVE_OK),
        ("POST", "/api/auth/payment/card",          403, PAY_REJECTED),
    ])
    _patch_async_client(monkeypatch, mock_client)

    client = TestClient(app)
    resp = client.post("/api/buy-ticket", json={"showtime_id": 542060})

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is False
    assert data["stage"] == "card_charge"
    assert data["code"] == "ED-024"
    assert "Tarjeta no permitida" in data["message"]
    assert data["estado"] == "Rechazada"
    assert data["factura"] == "PRO-1778083645-831"


def test_buy_ticket_missing_card_config(monkeypatch) -> None:
    """If card env vars are missing, fail fast at card_charge stage."""
    monkeypatch.setenv("PROCINAL_DOCUMENTO", "00000000")
    monkeypatch.setenv("PROCINAL_CLAVE", "test-fixture-pw")
    monkeypatch.setenv("PROCINAL_EMAIL", "test@felixpago.com")
    monkeypatch.setenv("PROCINAL_CARD_NUMBER", "")
    monkeypatch.setenv("PROCINAL_CARD_EXP_MONTH", "")
    monkeypatch.setenv("PROCINAL_CARD_EXP_YEAR", "")
    monkeypatch.setenv("PROCINAL_CARD_CVC", "")
    from app.config import get_settings
    get_settings.cache_clear()
    import app.services.procinal_client as pc
    pc._jwt_cache = None

    mock_client = _make_request_router([
        ("POST", "/api/auth/login",                 200, LOGIN_OK),
        ("GET",  "/api/showtimes/542060",           200, SHOWTIME_DETAIL),
        ("POST", "/api/auth/payment/reservation",   200, RESERVE_OK),
    ])
    _patch_async_client(monkeypatch, mock_client)

    client = TestClient(app)
    resp = client.post("/api/buy-ticket", json={"showtime_id": 542060})

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert data["stage"] == "card_charge"
    assert "PROCINAL_CARD" in data["message"]
