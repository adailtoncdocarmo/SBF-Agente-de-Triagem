"""Schemas de saída da API (ranking e ficha) — o que o frontend consome.

Montados pelo Python a partir das `Avaliacao` persistidas. A ficha entrega
exatamente o que o case pede (aderência + justificativa, destaques, lacunas,
recomendação) somado à rastreabilidade do framework (Portões, notas, recência).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.avaliacao import Avaliacao
from app.schemas.enums import Confianca, Recomendacao, ZonaDecisao


class LinhaRanking(BaseModel):
    """Uma linha do ranking (um candidato)."""

    candidato_id: int
    id_anonimo: str
    nome_arquivo: str
    nome_candidato: str | None = None
    posicao: int
    score_final: float
    percentil: int | None = None
    recomendacao: Recomendacao | None = None
    confianca: Confianca = Confianca.MEDIA
    # Zona + sinais para a lista única colorida (frontend filtra/colore por aqui).
    zona: ZonaDecisao | None = None
    sinais_fortes: list[str] = Field(default_factory=list)
    n_flags: int = 0
    # Avisos transparentes ("por isto está em Revisar / confirmar X").
    ressalvas: list[str] = Field(default_factory=list)


class FalhaCandidato(BaseModel):
    """Um currículo que falhou no processamento (para a faixa 'reenviar')."""

    candidato_id: int
    id_anonimo: str
    nome_arquivo: str
    nome_candidato: str | None = None
    motivo: str


class ContagensZona(BaseModel):
    """Contagem de candidatos por zona (para os chips de filtro)."""

    entra: int = 0
    avaliar: int = 0
    cai: int = 0


class RankingVaga(BaseModel):
    """Ranking acumulado de TODA a vaga — lista única ordenada por score.

    Cada novo lote recalibra a população inteira; este é o resultado que o RH vê.
    """

    vaga_id: int
    vaga: str
    total_avaliados: int
    taxa_auto_decisao: float
    contagens: ContagensZona = Field(default_factory=ContagensZona)
    linhas: list[LinhaRanking] = Field(default_factory=list)
    falhas: list[FalhaCandidato] = Field(default_factory=list)


class FichaCandidato(BaseModel):
    """Ficha rastreável de um candidato (clique na linha do ranking)."""

    candidato_id: int
    id_anonimo: str
    nome_candidato: str | None = None
    nome_arquivo: str
    vaga: str
    posicao: int | None = None
    total_lote: int | None = None
    score_final: float
    percentil: int | None = None
    recomendacao: Recomendacao | None = None
    confianca: Confianca = Confianca.MEDIA
    zona: ZonaDecisao | None = None
    justificativa: str = ""
    orientacao: str = ""
    destaques: list[str] = Field(default_factory=list)
    lacunas: list[str] = Field(default_factory=list)
    # True quando o currículo original (PDF/TXT/DOCX) está guardado para visualização.
    cv_disponivel: bool = False
    avaliacao: Avaliacao
