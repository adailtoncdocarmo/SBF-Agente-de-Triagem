"""Schema da saída do Agente Régua (LLM-facing).

A IA só **lê a vaga e propõe** estrutura: knockouts, quais critérios são
críticos, pesos sugeridos e competências detectadas. O Python (em
`agente_regua.py`) renormaliza os pesos para somar 100, casa as competências com
a tabela estática de volatilidade e monta a `Regua` final. A IA nunca decide a
nota — só estrutura a régua.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.enums import CriterioId
from app.schemas.regua import Knockout


class ReguaPropostaLLM(BaseModel):
    """Proposta de régua extraída da descrição da vaga pelo LLM."""

    knockouts: list[Knockout] = Field(default_factory=list)
    criterios_criticos: list[CriterioId] = Field(
        default_factory=list, description="1 a 3 ids de critérios que são o núcleo da vaga."
    )
    pesos_sugeridos: dict[str, int] = Field(
        default_factory=dict,
        description="Mapa critério→peso bruto, um por critério (o Python renormaliza para somar 100).",
    )
    competencias_detectadas: list[str] = Field(
        default_factory=list,
        description="Competências citadas na vaga (o Python casa com a tabela de volatilidade).",
    )
    justificativa: str = ""
