"""Provedores de LLM — abstração para o roteador multi-provedor.

O contrato entre IA e Python são os **schemas Pydantic**. Cada provedor
(qualquer um dos slots Principal/Secundária: Claude, OpenAI ou Gemini) adapta o
prompt e devolve o mesmo schema validado, para o roteador (`cliente_llm`) poder
cair de um para o outro em caso de timeout/indisponibilidade.
"""

from __future__ import annotations

from app.triagem.provedores.base import Provedor

# Modelo default por provedor (usado se nenhum modelo foi configurado).
_MODELO_DEFAULT = {
    "anthropic": "claude-sonnet-4-6",
    "openai": "gpt-4o-mini",
    "gemini": "gemini-2.0-flash",
}


def criar_provedor(provedor: str, api_key: str, modelo_default: str = "") -> Provedor | None:
    """Fábrica de provedores. Retorna None se sem chave ou SDK ausente."""
    if not api_key:
        return None
    padrao = modelo_default or _MODELO_DEFAULT.get(provedor, "")
    try:
        if provedor == "anthropic":
            from app.triagem.provedores.anthropic_p import ProvedorAnthropic

            return ProvedorAnthropic(api_key, padrao)
        if provedor == "openai":
            from app.triagem.provedores.openai_p import ProvedorOpenAI

            return ProvedorOpenAI(api_key, padrao)
        if provedor == "gemini":
            from app.triagem.provedores.gemini_p import ProvedorGemini

            return ProvedorGemini(api_key, padrao)
    except Exception:  # SDK do provedor ausente / falha de construção
        return None
    return None
