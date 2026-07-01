"""Smoke de integração: o app sobe com o lifespan (cria tabelas + fila) e
responde nos endpoints básicos de leitura."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_app_sobe_e_responde() -> None:
    # O context manager dispara o lifespan (criar_tabelas + fila.iniciar + retomada).
    with TestClient(app) as client:
        assert client.get("/api/health").json() == {"status": "ok"}

        vagas = client.get("/api/vagas")
        assert vagas.status_code == 200
        assert isinstance(vagas.json(), list)

        metricas = client.get("/api/metricas")
        assert metricas.status_code == 200
        assert "taxa_auto_decisao_media" in metricas.json()
