"""Schemas Pydantic (contratos de dados entre módulos) — Framework v3.

Separação central: schemas **LLM-facing** (só os sinais que a IA extrai) vs.
schemas **Python-computed** (nota, score, zona — calculados de forma
determinística). A nota e o ranking nunca saem do LLM.

Re-exporta os contratos mais usados para imports curtos
(`from app.schemas import Regua, Avaliacao`).
"""

from __future__ import annotations

from app.schemas.avaliacao import (
    Auditoria,
    Avaliacao,
    CalibracaoLote,
    CriterioAvaliado,
    Flags,
    RecenciaCalculada,
)
from app.schemas.enums import (
    Confianca,
    CriterioId,
    EstadoKnockout,
    EstagioCandidato,
    Recomendacao,
    ROTULOS_CRITERIOS,
    Severidade,
    StatusCandidato,
    StatusCritico,
    StatusLote,
    Volatilidade,
    ZonaDecisao,
)
from app.schemas.llm_comparacao import SaidaComparacaoLLM
from app.schemas.llm_flags import ClarezaLLM, FlagRiscoLLM, SaidaFlagsLLM
from app.schemas.llm_portao1 import KnockoutAvaliadoLLM, SaidaPortao1LLM
from app.schemas.llm_regua import ReguaPropostaLLM
from app.schemas.llm_scoring import NotaCriterioLLM, SaidaScoringLLM
from app.schemas.regua import (
    CriterioRegua,
    Knockout,
    Regua,
    Thresholds,
    VolatilidadeCompetencia,
)

__all__ = [
    "Auditoria",
    "Avaliacao",
    "CalibracaoLote",
    "CriterioAvaliado",
    "Flags",
    "RecenciaCalculada",
    "Confianca",
    "CriterioId",
    "EstadoKnockout",
    "EstagioCandidato",
    "Recomendacao",
    "ROTULOS_CRITERIOS",
    "Severidade",
    "StatusCandidato",
    "StatusCritico",
    "StatusLote",
    "Volatilidade",
    "ZonaDecisao",
    "SaidaComparacaoLLM",
    "ClarezaLLM",
    "FlagRiscoLLM",
    "SaidaFlagsLLM",
    "KnockoutAvaliadoLLM",
    "SaidaPortao1LLM",
    "ReguaPropostaLLM",
    "NotaCriterioLLM",
    "SaidaScoringLLM",
    "CriterioRegua",
    "Knockout",
    "Regua",
    "Thresholds",
    "VolatilidadeCompetencia",
]
