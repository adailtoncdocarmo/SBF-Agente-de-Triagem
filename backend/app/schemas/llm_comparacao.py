"""Schema do desempate pareado (pairwise) — LLM-facing.

Usado SÓ em empate técnico (|Δ score| ≤ 5). O Python randomiza a ordem A/B antes
de enviar (anula o viés de posição, que faz o pairwise "virar" ~35%). O resultado
apenas **ordena** empates — nunca altera a nota. A literatura aponta que o LLM
compara dois currículos melhor do que crava nota absoluta (Framework 6.4).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class SaidaComparacaoLLM(BaseModel):
    """Veredito da comparação direta entre dois candidatos (A vs B)."""

    vencedor: Literal["A", "B", "empate"]
    justificativa: str = ""
