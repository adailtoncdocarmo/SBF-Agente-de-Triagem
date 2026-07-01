"""Contrato comum dos provedores de LLM."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from pydantic import BaseModel


@dataclass
class ResultadoExtracao:
    """Saída de um provedor: o schema Pydantic validado + telemetria de tokens."""

    dados: BaseModel
    tokens_in: int = 0
    tokens_out: int = 0
    tokens_cache_read: int = 0


class RespostaInvalidaError(Exception):
    """A IA respondeu, mas a saída veio incompleta/truncada/sem schema parseável.

    É um erro **intermitente** (a geração é estocástica): vale retry no mesmo
    provedor — diferente de um provedor indisponível, que deve cair para o próximo.
    """


class Provedor(ABC):
    """Interface de um provedor de extração estruturada."""

    nome: str = "base"

    @property
    @abstractmethod
    def disponivel(self) -> bool:
        """True se o provedor tem credencial e pode ser usado."""

    @abstractmethod
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
        """Extrai e devolve o `schema` Pydantic validado (ou levanta em falha).

        `usar_thinking=False` desliga o raciocínio estendido (mais rápido), útil
        em chamadas interativas/estruturadas como a geração da régua.
        """
