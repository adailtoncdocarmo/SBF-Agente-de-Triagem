"""Provedor de fallback — Google Gemini (structured output com Pydantic).

Usado só quando a Claude falha/atrasa. Import preguiçoso do SDK `google-genai`.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.triagem.provedores.base import Provedor, ResultadoExtracao


class ProvedorGemini(Provedor):
    nome = "gemini"

    def __init__(self, api_key: str, modelo_default: str = "gemini-2.0-flash") -> None:
        self._modelo_default = modelo_default
        self._client = None
        if api_key:
            from google import genai  # import preguiçoso (dep de fallback)

            self._client = genai.Client(api_key=api_key)

    @property
    def disponivel(self) -> bool:
        return self._client is not None

    async def extrair(
        self,
        *,
        skill_text: str,
        conteudo: str,
        schema: type[BaseModel],
        modelo: str,
        max_tokens: int = 2048,
        usar_thinking: bool = True,  # ignorado (sem extended thinking aqui)
    ) -> ResultadoExtracao:
        assert self._client is not None
        resposta = await self._client.aio.models.generate_content(
            model=modelo or self._modelo_default,
            contents=conteudo,
            config={
                "system_instruction": skill_text,
                "response_mime_type": "application/json",
                "response_schema": schema,
                "max_output_tokens": max_tokens,
            },
        )
        dados = getattr(resposta, "parsed", None)
        if dados is None:
            dados = schema.model_validate_json(getattr(resposta, "text", "") or "{}")
        uso = getattr(resposta, "usage_metadata", None)
        return ResultadoExtracao(
            dados=dados,
            tokens_in=int(getattr(uso, "prompt_token_count", 0) or 0),
            tokens_out=int(getattr(uso, "candidates_token_count", 0) or 0),
        )
