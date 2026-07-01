"""Provedor de fallback — OpenAI (structured outputs com Pydantic).

Usado só quando a Claude falha/atrasa. Import preguiçoso do SDK `openai` para
não acoplar o caminho primário à dependência de fallback.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.triagem.provedores.base import Provedor, ResultadoExtracao


class ProvedorOpenAI(Provedor):
    nome = "openai"

    def __init__(self, api_key: str, modelo_default: str = "gpt-4o-mini") -> None:
        self._modelo_default = modelo_default
        self._client = None
        if api_key:
            from openai import AsyncOpenAI  # import preguiçoso (dep de fallback)

            self._client = AsyncOpenAI(api_key=api_key)

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
        resposta = await self._client.beta.chat.completions.parse(
            model=modelo or self._modelo_default,
            messages=[
                {"role": "system", "content": skill_text},
                {"role": "user", "content": conteudo},
            ],
            response_format=schema,
            max_tokens=max_tokens,
        )
        mensagem = resposta.choices[0].message
        dados = getattr(mensagem, "parsed", None)
        if dados is None:
            dados = schema.model_validate_json(mensagem.content or "{}")
        uso = getattr(resposta, "usage", None)
        return ResultadoExtracao(
            dados=dados,
            tokens_in=int(getattr(uso, "prompt_tokens", 0) or 0),
            tokens_out=int(getattr(uso, "completion_tokens", 0) or 0),
        )
