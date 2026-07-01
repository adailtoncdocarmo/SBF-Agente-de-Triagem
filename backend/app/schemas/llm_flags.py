"""Schema das flags de risco e clareza — LLM-facing.

Flags NÃO entram no score (Framework Parte 4). Risco e clareza modulam
**confiança e roteamento** para revisão humana, não a nota do candidato. A IA
sinaliza; o Python decide o que isso significa para a zona de decisão.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.enums import Confianca, Severidade


class FlagRiscoLLM(BaseModel):
    """Um sinal de risco detectado no currículo."""

    descricao: str
    severidade: Severidade
    acao: str = Field(
        default="", description="Ação sugerida (ex.: 'validar na entrevista')."
    )


class ClarezaLLM(BaseModel):
    """Clareza/completude do CV → confiança da avaliação (não mede qualidade)."""

    nivel: Confianca = Confianca.MEDIA
    confianca_avaliacao: Confianca = Confianca.MEDIA


class SaidaFlagsLLM(BaseModel):
    """Saída completa do estágio 3."""

    risco: list[FlagRiscoLLM] = Field(default_factory=list)
    clareza: ClarezaLLM = Field(default_factory=ClarezaLLM)
