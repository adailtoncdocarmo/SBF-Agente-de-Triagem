"""Schema da saída do Portão 1 (knockout em 3 estados) — LLM-facing.

A IA classifica cada requisito eliminatório em atende / não atende /
não evidenciado, sempre citando evidência literal do CV. **A IA não bloqueia**
ninguém: o Python (em `zonas.py`) decide o descarte só quando "não atende" é
confirmado; "não evidenciado" segue no ranking e vira validação apenas se o
candidato disputaria vaga.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.enums import EstadoKnockout


class KnockoutAvaliadoLLM(BaseModel):
    """Avaliação de um requisito knockout contra o currículo."""

    requisito: str
    estado: EstadoKnockout
    # Preenchidos pelo Python a partir da régua (não é a IA que decide): só um
    # requisito objetivo verificável pode eliminar quando "não atende"; e o
    # `tipico_no_cv` decide se a ausência (não evidenciado) penaliza ou não.
    objetivo: bool = False
    tipico_no_cv: bool = True
    evidencias: list[str] = Field(
        default_factory=list,
        description="Citações literais do CV que sustentam o estado (vazio se não evidenciado).",
    )


class SaidaPortao1LLM(BaseModel):
    """Saída completa do estágio 1 para um currículo."""

    knockouts: list[KnockoutAvaliadoLLM] = Field(default_factory=list)
