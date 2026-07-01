"""Camada de configuração em runtime (low-code).

Sobrepõe-se ao `.env`/`config.py`: precedência **banco (SQLite) → .env/config → padrão**.
Lida em tempo de execução (cada operação cria um cliente novo → pega a config nova sem
restart). Cobre as duas chaves de API **provider-agnostic** (Principal e Secundária —
cada uma com provedor + chave + modelo), thresholds, concorrência e timeout.

Não importa o roteador/orquestrador (evita ciclo).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from app.config import configuracoes
from app.database import SessionLocal
from app.models_db import ConfiguracaoRuntime

# Modelo default por provedor (usado quando não há modelo configurado).
MODELO_DEFAULT_PROVEDOR: dict[str, str] = {
    "anthropic": "claude-sonnet-4-6",
    "openai": "gpt-4o-mini",
    "gemini": "gemini-2.0-flash",
}


@dataclass
class ConfigProvedor:
    """Um slot de provedor de IA (Principal ou Secundária)."""

    provedor: str  # 'anthropic' | 'openai' | 'gemini'
    api_key: str
    modelo: str
    rate_in: float
    rate_out: float


def _env_key(provedor: str) -> str:
    """Chave do provedor a partir do ambiente (fallback à config do banco)."""
    if provedor == "anthropic":
        return configuracoes.anthropic_api_key
    if provedor == "openai":
        return os.environ.get("OPENAI_API_KEY", "")
    if provedor == "gemini":
        return os.environ.get("GEMINI_API_KEY", "")
    return ""


# --------------------------------------------------------------------------- #
# Acesso genérico ao key/value persistido (resiliente: cai no default em erro)
# --------------------------------------------------------------------------- #
def _get(chave: str, default: object) -> object:
    try:
        with SessionLocal() as sessao:
            linha = sessao.get(ConfiguracaoRuntime, chave)
            if linha is None:
                return default
            return linha.valor_json.get("v", default)
    except Exception:
        return default


def _set(chave: str, valor: object) -> None:
    with SessionLocal() as sessao:
        linha = sessao.get(ConfiguracaoRuntime, chave)
        if linha is None:
            sessao.add(ConfiguracaoRuntime(chave=chave, valor_json={"v": valor}))
        else:
            linha.valor_json = {"v": valor}
        sessao.commit()


# --------------------------------------------------------------------------- #
# Provedores (Principal / Secundária)
# --------------------------------------------------------------------------- #
def _config_provedor(dados: dict, default_provedor: str) -> ConfigProvedor:
    provedor = str(dados.get("provedor", default_provedor))
    api_key = str(dados.get("api_key", "") or "") or _env_key(provedor)
    # chave legada (UI antiga guardava só a da Anthropic em 'anthropic_api_key')
    if not api_key and provedor == "anthropic":
        api_key = str(_get("anthropic_api_key", "") or "")
    modelo = str(dados.get("modelo", "") or "") or MODELO_DEFAULT_PROVEDOR.get(provedor, "")
    return ConfigProvedor(
        provedor=provedor,
        api_key=api_key,
        modelo=modelo,
        rate_in=float(dados.get("rate_in", configuracoes.custo_fallback_in)),
        rate_out=float(dados.get("rate_out", configuracoes.custo_fallback_out)),
    )


def obter_principal() -> ConfigProvedor:
    """Slot Principal (default: Anthropic)."""
    dados = _get("principal", {})
    if not isinstance(dados, dict):
        dados = {}
    return _config_provedor(dados, "anthropic")


def obter_secundaria() -> ConfigProvedor | None:
    """Slot Secundário (reserva). None se desligado ou sem chave."""
    dados = _get("secundaria", None)
    if not isinstance(dados, dict) or not dados.get("habilitado"):
        return None
    cfg = _config_provedor(dados, "openai")
    return cfg if cfg.api_key else None


def obter_secundaria_bruta() -> ConfigProvedor | None:
    """Slot Secundário **independente de estar habilitado** — para testar/remover.

    Testar uma chave não exige que a reserva esteja ativa; usamos isto para
    resolver a chave salva mesmo com a reserva desligada.
    """
    dados = _get("secundaria", None)
    if not isinstance(dados, dict):
        return None
    cfg = _config_provedor(dados, "openai")
    return cfg if cfg.api_key else None


def remover_chave(slot: str) -> None:
    """Limpa a chave de um slot (`principal` | `secundaria`).

    A reserva também é desligada ao remover. A chave legada (UI antiga, só
    Anthropic) é limpa junto no slot principal. O `.env` continua sendo uma
    fonte de fallback (nível de código) — removível só lá.
    """
    if slot not in ("principal", "secundaria"):
        raise ValueError(f"Slot inválido: {slot}")
    dados = _get(slot, {}) or {}
    if not isinstance(dados, dict):
        dados = {}
    dados = dict(dados)
    dados["api_key"] = ""
    if slot == "secundaria":
        dados["habilitado"] = False
    _set(slot, dados)
    if slot == "principal":
        _set("anthropic_api_key", "")  # limpa também a chave legada


# --------------------------------------------------------------------------- #
# Demais parâmetros
# --------------------------------------------------------------------------- #
def obter_thresholds_default() -> dict:
    return dict(
        _get(
            "thresholds",
            {
                "corte_verde": configuracoes.corte_verde_default,
                "corte_amarelo": configuracoes.corte_amarelo_default,
                "alvo_auto_decisao": configuracoes.alvo_auto_decisao_default,
            },
        )
    )


def obter_concorrencia() -> int:
    return int(_get("concorrencia_cvs", configuracoes.concorrencia_cvs))


def obter_timeout_llm() -> float:
    return float(_get("timeout_llm", configuracoes.timeout_llm_segundos))


# --------------------------------------------------------------------------- #
# Escrita das configs (a partir do payload do router) + snapshot mascarado
# --------------------------------------------------------------------------- #
def _merge_provedor(chave: str, novo: dict) -> None:
    atual = _get(chave, {}) or {}
    if not isinstance(atual, dict):
        atual = {}
    merged = dict(atual)
    for campo in ("provedor", "modelo", "rate_in", "rate_out", "habilitado"):
        if campo in novo and novo[campo] is not None:
            merged[campo] = novo[campo]
    if novo.get("api_key"):  # só sobrescreve se enviada e não-vazia
        merged["api_key"] = novo["api_key"]
    _set(chave, merged)


def _clamp(valor: float, lo: float, hi: float) -> float:
    """Limita `valor` ao intervalo [lo, hi]."""
    return max(lo, min(hi, valor))


def salvar_config(payload: dict) -> None:
    """Persiste os campos enviados, com clamp de faixa (defesa em profundidade).

    O Pydantic do router já rejeita (422) fora de faixa; este clamp protege
    chamadas diretas (testes/código interno) de persistir valores inválidos.
    Thresholds são **mesclados** (PATCH parcial não apaga os ausentes).
    """
    if payload.get("principal"):
        _merge_provedor("principal", payload["principal"])
    if payload.get("secundaria"):
        _merge_provedor("secundaria", payload["secundaria"])
    if payload.get("thresholds") is not None:
        atual = obter_thresholds_default()
        novo = payload["thresholds"]
        if novo.get("corte_verde") is not None:
            atual["corte_verde"] = int(_clamp(novo["corte_verde"], 0, 100))
        if novo.get("corte_amarelo") is not None:
            atual["corte_amarelo"] = int(_clamp(novo["corte_amarelo"], 0, 100))
        if novo.get("alvo_auto_decisao") is not None:
            atual["alvo_auto_decisao"] = float(_clamp(novo["alvo_auto_decisao"], 0.0, 1.0))
        _set("thresholds", atual)
    if payload.get("concorrencia_cvs") is not None:
        _set("concorrencia_cvs", int(_clamp(int(payload["concorrencia_cvs"]), 1, 16)))
    if payload.get("timeout_llm") is not None:
        _set("timeout_llm", float(_clamp(float(payload["timeout_llm"]), 1.0, 300.0)))


def mascarar(chave: str) -> str:
    """Mascara uma chave de API (mostra só os últimos 4 dígitos)."""
    if not chave:
        return ""
    if len(chave) <= 4:
        return "••••"
    return f"••••{chave[-4:]}"


def snapshot() -> dict:
    """Estado atual das configs para o GET — chaves SEMPRE mascaradas."""
    principal = obter_principal()
    sec = _get("secundaria", {}) or {}
    if not isinstance(sec, dict):
        sec = {}
    sec_provedor = str(sec.get("provedor", "openai"))
    sec_key = str(sec.get("api_key", "") or "")
    return {
        "api_key_configurada": bool(principal.api_key),
        "principal": {
            "provedor": principal.provedor,
            "modelo": principal.modelo,
            "api_key_configurada": bool(principal.api_key),
            "api_key_mascarada": mascarar(principal.api_key),
        },
        "secundaria": {
            "habilitado": bool(sec.get("habilitado", False)),
            "provedor": sec_provedor,
            "modelo": str(sec.get("modelo", "") or "") or MODELO_DEFAULT_PROVEDOR.get(sec_provedor, ""),
            "api_key_configurada": bool(sec_key),
            "api_key_mascarada": mascarar(sec_key),
        },
        "thresholds": obter_thresholds_default(),
        "concorrencia_cvs": obter_concorrencia(),
        "timeout_llm": obter_timeout_llm(),
    }
