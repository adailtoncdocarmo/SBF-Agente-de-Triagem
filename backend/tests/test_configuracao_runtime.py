"""Testes da configuração em runtime (slots Principal/Secundária, máscara)."""

from __future__ import annotations

import pytest

from app import configuracao_runtime as cfg
from app.database import SessionLocal, criar_tabelas
from app.models_db import ConfiguracaoRuntime


@pytest.fixture(autouse=True)
def _limpar_config():
    criar_tabelas()
    yield
    with SessionLocal() as s:
        s.query(ConfiguracaoRuntime).delete()
        s.commit()


def test_principal_default_anthropic() -> None:
    p = cfg.obter_principal()
    assert p.provedor == "anthropic"
    assert p.modelo == "claude-sonnet-4-6"
    assert cfg.obter_secundaria() is None


def test_principal_qualquer_provedor() -> None:
    cfg.salvar_config(
        {"principal": {"provedor": "openai", "modelo": "gpt-4o", "api_key": "sk-openai9999"}}
    )
    p = cfg.obter_principal()
    assert p.provedor == "openai" and p.modelo == "gpt-4o" and p.api_key == "sk-openai9999"
    snap = cfg.snapshot()["principal"]
    assert snap["provedor"] == "openai" and snap["api_key_mascarada"].endswith("9999")
    assert "openai9999" not in snap["api_key_mascarada"]


def test_chave_vazia_nao_sobrescreve() -> None:
    cfg.salvar_config({"principal": {"provedor": "anthropic", "api_key": "sk-ant-aaaa1111"}})
    cfg.salvar_config({"principal": {"modelo": "claude-opus-4-8"}})  # sem chave → mantém
    p = cfg.obter_principal()
    assert p.api_key == "sk-ant-aaaa1111" and p.modelo == "claude-opus-4-8"


def test_secundaria_liga_e_mascara() -> None:
    assert cfg.obter_secundaria() is None
    cfg.salvar_config(
        {"secundaria": {"habilitado": True, "provedor": "gemini", "api_key": "sk-gem", "modelo": "gemini-2.0-flash"}}
    )
    s = cfg.obter_secundaria()
    assert s is not None and s.provedor == "gemini" and s.api_key == "sk-gem"
    snap = cfg.snapshot()["secundaria"]
    assert snap["habilitado"] and snap["api_key_configurada"]
    assert "sk-gem" not in snap["api_key_mascarada"]


def test_secundaria_desligada_retorna_none_mas_guarda_dados() -> None:
    cfg.salvar_config(
        {"secundaria": {"habilitado": False, "provedor": "openai", "api_key": "sk-x", "modelo": "gpt-4o-mini"}}
    )
    assert cfg.obter_secundaria() is None  # desligada
    snap = cfg.snapshot()["secundaria"]  # mas os dados seguem visíveis (mascarados)
    assert snap["provedor"] == "openai" and snap["api_key_configurada"] is True


def test_salvar_config_faz_clamp_de_faixa() -> None:
    # Defesa em profundidade: chamadas diretas (sem o Pydantic do router) não
    # devem persistir valores fora de faixa.
    cfg.salvar_config({"concorrencia_cvs": 999})
    assert cfg.obter_concorrencia() == 16
    cfg.salvar_config({"concorrencia_cvs": 0})
    assert cfg.obter_concorrencia() == 1
    cfg.salvar_config({"thresholds": {"corte_verde": 150, "alvo_auto_decisao": 9.0}})
    th = cfg.obter_thresholds_default()
    assert th["corte_verde"] == 100 and th["alvo_auto_decisao"] == 1.0


def test_salvar_config_thresholds_parcial_preserva_ausentes() -> None:
    cfg.salvar_config({"thresholds": {"corte_verde": 70}})  # só um campo
    th = cfg.obter_thresholds_default()
    assert th["corte_verde"] == 70
    assert "corte_amarelo" in th and "alvo_auto_decisao" in th  # não apagados


def test_secundaria_bruta_resolve_mesmo_desligada() -> None:
    # Testar uma chave não exige ativar a reserva: a chave salva deve ser resolvível.
    cfg.salvar_config(
        {"secundaria": {"habilitado": False, "provedor": "openai", "api_key": "sk-oai-bruta", "modelo": "gpt-4o-mini"}}
    )
    assert cfg.obter_secundaria() is None  # gated por habilitado
    bruta = cfg.obter_secundaria_bruta()
    assert bruta is not None and bruta.provedor == "openai" and bruta.api_key == "sk-oai-bruta"


def test_remover_chave_limpa_e_desliga() -> None:
    cfg.salvar_config(
        {"secundaria": {"habilitado": True, "provedor": "openai", "api_key": "sk-oai-rm", "modelo": "gpt-4o-mini"}}
    )
    cfg.remover_chave("secundaria")
    sec = cfg._get("secundaria", {})
    assert sec.get("api_key") == "" and sec.get("habilitado") is False


def test_remover_chave_slot_invalido_levanta() -> None:
    with pytest.raises(ValueError):
        cfg.remover_chave("inexistente")
