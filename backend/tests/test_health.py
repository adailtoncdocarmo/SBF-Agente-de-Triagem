"""Teste de fumaça: a API de saúde responde 200 com o payload esperado."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_responde_ok() -> None:
    """`GET /api/health` deve retornar 200 e {"status": "ok"}."""
    resposta = client.get("/api/health")
    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ok"}


def test_rota_api_desconhecida_retorna_404() -> None:
    """Rotas `/api/*` inexistentes não devem cair no fallback do SPA."""
    resposta = client.get("/api/rota-que-nao-existe")
    assert resposta.status_code == 404
