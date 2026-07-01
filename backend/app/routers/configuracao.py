"""Endpoints de Configuração (low-code) — chaves de API (Principal/Secundária,
qualquer provedor) e parâmetros de avaliação, tudo editável pela UI sem mexer no
código nem reiniciar.

Chaves de API **nunca** são retornadas em claro (só mascaradas).
"""

from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app import configuracao_runtime as cfg
from app.triagem.reprocesso import aplicar_thresholds_a_todas_vagas

logger = logging.getLogger("routers.configuracao")

router = APIRouter(tags=["configuracao"])


# --------------------------------------------------------------------------- #
# Payloads
# --------------------------------------------------------------------------- #
class ProvedorPayload(BaseModel):
    provedor: Literal["anthropic", "openai", "gemini"] | None = None
    api_key: str | None = None
    modelo: str | None = None
    habilitado: bool | None = None  # usado só na Secundária
    rate_in: float | None = Field(default=None, ge=0)
    rate_out: float | None = Field(default=None, ge=0)


class ThresholdsPayload(BaseModel):
    """Cortes de avaliação editáveis (campos opcionais → PATCH parcial), com bounds.

    Espelha os bounds de `schemas.regua.Thresholds`; evita persistir valores fora
    de faixa — regra "nunca dict solto" do CLAUDE.md.
    """

    corte_verde: int | None = Field(default=None, ge=0, le=100)
    corte_amarelo: int | None = Field(default=None, ge=0, le=100)
    alvo_auto_decisao: float | None = Field(default=None, ge=0.0, le=1.0)


class ConfiguracaoPayload(BaseModel):
    principal: ProvedorPayload | None = None
    secundaria: ProvedorPayload | None = None
    thresholds: ThresholdsPayload | None = None
    concorrencia_cvs: int | None = Field(default=None, ge=1, le=16)
    timeout_llm: float | None = Field(default=None, gt=0, le=300)


class TestarChavePayload(BaseModel):
    provedor: Literal["anthropic", "openai", "gemini"] = "anthropic"
    api_key: str | None = None  # se ausente, usa a configurada (Principal/Secundária)


class RespostaTesteChave(BaseModel):
    """Resultado do teste de conexão de uma chave (tipado — nunca dict solto)."""

    ok: bool
    mensagem: str


# --------------------------------------------------------------------------- #
# Configuração geral
# --------------------------------------------------------------------------- #
@router.get("/configuracao")
def obter_configuracao() -> dict:
    """Snapshot da configuração atual (chaves mascaradas)."""
    return cfg.snapshot()


@router.put("/configuracao")
def salvar_configuracao(dados: ConfiguracaoPayload) -> dict:
    """Salva os campos enviados (chaves vazias mantêm a atual).

    Se os **cortes de avaliação** (thresholds) mudarem, aplica-os a todas as
    vagas e recalcula deterministicamente (sem IA) — reposicionando os candidatos
    já avaliados conforme o novo percentil de shortlist / piso.
    """
    payload = dados.model_dump(exclude_none=True)
    cfg.salvar_config(payload)
    resposta = cfg.snapshot()
    if payload.get("thresholds"):
        resposta["vagas_recalculadas"] = aplicar_thresholds_a_todas_vagas(
            payload["thresholds"]
        )
    return resposta


@router.delete("/configuracao/provedor/{slot}")
def remover_chave(slot: Literal["principal", "secundaria"]) -> dict:
    """Remove a chave de um slot (Principal/Secundária). Retorna o snapshot."""
    cfg.remover_chave(slot)
    return cfg.snapshot()


def _resolver_chave(provedor: str, informada: str | None) -> str:
    """Resolve a chave a testar: a informada, senão a do slot com aquele provedor."""
    if informada:
        return informada
    principal = cfg.obter_principal()
    if principal.provedor == provedor and principal.api_key:
        return principal.api_key
    # Usa a chave salva da reserva MESMO desligada — testar não exige ativar.
    secundaria = cfg.obter_secundaria_bruta()
    if secundaria and secundaria.provedor == provedor and secundaria.api_key:
        return secundaria.api_key
    return cfg._env_key(provedor)


@router.post("/configuracao/testar-chave")
async def testar_chave(dados: TestarChavePayload) -> RespostaTesteChave:
    """Valida a chave de um provedor com uma chamada mínima."""
    chave = _resolver_chave(dados.provedor, dados.api_key)
    if not chave:
        return RespostaTesteChave(ok=False, mensagem=f"Nenhuma chave configurada para {dados.provedor}.")
    try:
        if dados.provedor == "anthropic":
            import anthropic

            cliente = anthropic.AsyncAnthropic(api_key=chave)
            await cliente.messages.count_tokens(
                model=cfg.MODELO_DEFAULT_PROVEDOR["anthropic"],
                messages=[{"role": "user", "content": "ping"}],
            )
            return RespostaTesteChave(ok=True, mensagem="Conexão OK (Claude).")
        if dados.provedor == "openai":
            from openai import AsyncOpenAI

            await AsyncOpenAI(api_key=chave).models.list()
            return RespostaTesteChave(ok=True, mensagem="Conexão OK (OpenAI).")
        from google import genai

        list(genai.Client(api_key=chave).models.list())
        return RespostaTesteChave(ok=True, mensagem="Conexão OK (Gemini).")
    except Exception:  # noqa: BLE001 — teste de conexão; loga a causa, não vaza ao cliente
        # Detalhe completo só no log do servidor; ao cliente, mensagem genérica
        # (não vaza tipo de exceção nem trecho de chave/erro do provedor).
        logger.exception("Falha ao testar a chave do provedor %s.", dados.provedor)
        return RespostaTesteChave(
            ok=False,
            mensagem="Falha na conexão — verifique o provedor e a chave configurada.",
        )
