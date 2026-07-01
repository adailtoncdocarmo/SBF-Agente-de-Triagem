"""Provedor primário — Anthropic / Claude (saída estruturada via messages.parse)."""

from __future__ import annotations

import anthropic
from pydantic import BaseModel

from app.triagem.provedores.base import Provedor, RespostaInvalidaError, ResultadoExtracao


class ProvedorAnthropic(Provedor):
    """Claude com `messages.parse` + prompt caching da skill + thinking adaptativo."""

    nome = "anthropic"

    def __init__(self, api_key: str, modelo_default: str = "claude-sonnet-4-6") -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key) if api_key else None
        self._modelo_default = modelo_default

    @property
    def disponivel(self) -> bool:
        return self._client is not None

    @staticmethod
    def _suporta_thinking(modelo: str) -> bool:
        nome = modelo.lower()
        return "sonnet" in nome or "opus" in nome

    async def extrair(
        self,
        *,
        skill_text: str,
        conteudo: str,
        schema: type[BaseModel],
        modelo: str,
        max_tokens: int = 2048,
        usar_thinking: bool = True,
    ) -> ResultadoExtracao:
        assert self._client is not None
        modelo = modelo or self._modelo_default
        system = [{"type": "text", "text": skill_text, "cache_control": {"type": "ephemeral"}}]
        kwargs: dict[str, object] = {
            "model": modelo,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": conteudo}],
            "output_format": schema,
        }
        if usar_thinking and self._suporta_thinking(modelo):
            kwargs["thinking"] = {"type": "adaptive"}

        resposta = await self._client.messages.parse(**kwargs)
        # Saída truncada (bateu o teto de tokens) → JSON incompleto/inparseável.
        if getattr(resposta, "stop_reason", None) == "max_tokens":
            raise RespostaInvalidaError("Resposta truncada (max_tokens) — saída incompleta.")
        dados = self._extrair_saida(resposta, schema)
        uso = getattr(resposta, "usage", None)
        return ResultadoExtracao(
            dados=dados,
            tokens_in=int(getattr(uso, "input_tokens", 0) or 0),
            tokens_out=int(getattr(uso, "output_tokens", 0) or 0),
            tokens_cache_read=int(getattr(uso, "cache_read_input_tokens", 0) or 0),
        )

    @staticmethod
    def _extrair_saida(resposta: object, schema: type[BaseModel]) -> BaseModel:
        conteudo = getattr(resposta, "content", []) or []
        for bloco in conteudo:
            parsed = getattr(bloco, "parsed_output", None)
            if parsed is not None:
                return parsed
        for bloco in conteudo:
            if getattr(bloco, "type", None) == "text":
                return schema.model_validate_json(bloco.text)
        raise RespostaInvalidaError("Resposta da Claude sem saída estruturada parseável.")
