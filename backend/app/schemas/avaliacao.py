"""Schema da Avaliação final de um candidato — Python-computed.

Espelha o JSON da Parte 8 do framework. Tudo aqui é produzido pelo Python a
partir dos sinais do LLM: o `score_final` é a soma determinística das pontuações,
a `zona_decisao` vem da classificação das 3 zonas, e cada valor carrega evidência.
Os campos `calibracao_lote` e `zona_decisao` ficam `None` até os estágios
lote-level (6 e 8), pois dependem de todos os CVs do lote.
"""

from __future__ import annotations

from pydantic import AliasChoices, BaseModel, Field

from app.schemas.enums import (
    Confianca,
    Recomendacao,
    StatusCritico,
    Volatilidade,
    ZonaDecisao,
)
from app.schemas.llm_flags import ClarezaLLM, FlagRiscoLLM
from app.schemas.llm_portao1 import KnockoutAvaliadoLLM


class RecenciaCalculada(BaseModel):
    """Recência aplicada a um critério (Python, não IA)."""

    volatilidade: Volatilidade
    ultimo_uso: str | None = None
    modificador: int = Field(default=0, le=0, ge=-1, description="0 ou -1 (Framework Parte 3).")


class CriterioAvaliado(BaseModel):
    """Resultado completo de um critério: nota + cálculo + rastreabilidade."""

    criterio: str
    rotulo: str
    critico: bool
    peso: int
    nota_0_4: int = Field(ge=0, le=4)
    nota_minima: int = Field(
        # Aceita a chave antiga `piso_critico_senioridade` para avaliações já salvas;
        # serializa sempre como `nota_minima` (saída explícita).
        validation_alias=AliasChoices("nota_minima", "piso_critico_senioridade"),
        serialization_alias="nota_minima",
        description="Nota mínima exigida no critério decisivo (0 se não-crítico).",
    )
    status_critico: StatusCritico
    confianca_criterio: Confianca
    recencia: RecenciaCalculada
    pontuacao: float = Field(description="peso × nota ÷ 4 (cálculo determinístico).")
    justificativa_nota: str = Field(
        default="", description="Por que a IA deu essa nota ao critério (texto curto)."
    )
    evidencias: list[str] = Field(default_factory=list)
    lacunas: list[str] = Field(default_factory=list)


class CalibracaoLote(BaseModel):
    """Posição do candidato na distribuição do lote (estágio 6, lote-level)."""

    percentil: int = Field(ge=0, le=100)
    piso_absoluto: int
    empate_tecnico: bool = False
    comparacao_direta: bool = False


class Flags(BaseModel):
    """Flags de risco + clareza (não entram no score)."""

    risco: list[FlagRiscoLLM] = Field(default_factory=list)
    clareza: ClarezaLLM = Field(default_factory=ClarezaLLM)


class Auditoria(BaseModel):
    """Marcadores de auditoria de justiça (Framework Parte 7)."""

    dados_sensiveis_no_score: bool = False
    proxies_monitorados: bool = True


class Avaliacao(BaseModel):
    """Avaliação rastreável de um candidato (Framework Parte 8)."""

    candidato: str = Field(description="ID anonimizado (sem PII).")
    vaga: str
    versao_framework: str = "v3-final"

    portao_1: list[KnockoutAvaliadoLLM] = Field(default_factory=list)
    criterios: list[CriterioAvaliado] = Field(default_factory=list)
    score_final: float = Field(default=0.0, ge=0.0, le=100.0)

    calibracao_lote: CalibracaoLote | None = None  # preenchido no estágio 6
    flags: Flags = Field(default_factory=Flags)

    zona_decisao: ZonaDecisao | None = None  # preenchido no estágio 8
    rejeicao_automatica_permitida: bool = False
    motivo_zona: str = ""
    # Avisos transparentes ("selos") exibidos no card — ex.: "confirmar requisito X".
    # Podem rebaixar um verde para amarelo, mas nunca eliminam sozinhos.
    ressalvas: list[str] = Field(default_factory=list)
    recomendacao: Recomendacao | None = None
    confianca: Confianca = Confianca.MEDIA
    auditoria: Auditoria = Field(default_factory=Auditoria)

    # Textos enriquecidos pela IA (estágio "sintese"). Ficam vazios até a síntese
    # rodar; a ficha cai no texto de template quando vazios.
    sintese_aderencia: str = Field(
        default="", description="Por que o candidato adere (ou não) ao perfil — até ~3 linhas."
    )
    sintese_recomendacao: str = Field(
        default="", description="Orientação ao RH sobre como endereçar o perfil — até ~3 linhas."
    )
