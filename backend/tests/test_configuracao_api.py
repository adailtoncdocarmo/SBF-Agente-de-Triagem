"""Testes da API de Configuração (via TestClient): máscara, salvar, thresholds."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models_db import ConfiguracaoRuntime


@pytest.fixture(autouse=True)
def _limpar_config():
    yield
    with SessionLocal() as s:
        s.query(ConfiguracaoRuntime).delete()
        s.commit()


def test_get_configuracao_mascara_chave() -> None:
    with TestClient(app) as client:
        body = client.get("/api/configuracao").json()
        assert "api_key_configurada" in body
        assert "principal" in body and "secundaria" in body
        # nunca há chave em claro no payload
        assert "api_key" not in body["principal"]
        assert "api_key_mascarada" in body["principal"]


def test_put_salva_principal_e_reflete_mascarado() -> None:
    with TestClient(app) as client:
        client.put(
            "/api/configuracao",
            json={
                "principal": {
                    "provedor": "anthropic",
                    "modelo": "claude-opus-4-8",
                    "api_key": "sk-ant-zzzz1111",
                }
            },
        )
        body = client.get("/api/configuracao").json()
        assert body["principal"]["provedor"] == "anthropic"
        assert body["principal"]["modelo"] == "claude-opus-4-8"
        assert body["api_key_configurada"] is True
        assert body["principal"]["api_key_mascarada"].endswith("1111")
        assert "zzzz1111" not in body["principal"]["api_key_mascarada"]


def test_put_principal_openai() -> None:
    with TestClient(app) as client:
        client.put(
            "/api/configuracao",
            json={"principal": {"provedor": "openai", "modelo": "gpt-4o", "api_key": "sk-oai-2222"}},
        )
        body = client.get("/api/configuracao").json()
        assert body["principal"]["provedor"] == "openai"
        assert body["principal"]["modelo"] == "gpt-4o"
        assert body["principal"]["api_key_mascarada"].endswith("2222")


def test_thresholds_e_bounds_fora_de_faixa_rejeitados() -> None:
    with TestClient(app) as client:
        assert client.put("/api/configuracao", json={"concorrencia_cvs": 999}).status_code == 422
        assert client.put("/api/configuracao", json={"timeout_llm": 0}).status_code == 422
        assert (
            client.put(
                "/api/configuracao", json={"thresholds": {"corte_verde": 150}}
            ).status_code
            == 422
        )


def test_thresholds_validos_persistem() -> None:
    with TestClient(app) as client:
        client.put(
            "/api/configuracao",
            json={"thresholds": {"corte_verde": 70, "corte_amarelo": 40, "alvo_auto_decisao": 0.5}},
        )
        body = client.get("/api/configuracao").json()
        assert body["thresholds"]["corte_verde"] == 70
        assert body["thresholds"]["alvo_auto_decisao"] == 0.5


def test_remover_chave_secundaria() -> None:
    with TestClient(app) as client:
        client.put(
            "/api/configuracao",
            json={
                "secundaria": {
                    "habilitado": True,
                    "provedor": "openai",
                    "api_key": "sk-oai-endp9999",
                    "modelo": "gpt-4o-mini",
                }
            },
        )
        assert client.get("/api/configuracao").json()["secundaria"]["api_key_configurada"] is True
        body = client.delete("/api/configuracao/provedor/secundaria").json()
        assert body["secundaria"]["api_key_configurada"] is False
        assert body["secundaria"]["habilitado"] is False


def test_remover_chave_slot_invalido_422() -> None:
    with TestClient(app) as client:
        assert client.delete("/api/configuracao/provedor/xxx").status_code == 422
