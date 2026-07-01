"""Schema da saída de pontuação dos 7 critérios — LLM-facing.

A IA atribui nota **0-4 inteira** a cada critério, ancorada nas tabelas de força
de evidência (Framework Parte 3), citando evidências e lacunas, e informa o ano
do último uso da competência (para o Python aplicar recência). A IA não calcula
score nem aplica recência — só extrai a nota ancorada e os sinais.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.schemas.enums import Confianca, CriterioId


class NotaCriterioLLM(BaseModel):
    """Nota 0-4 (inteira) de um critério, com evidências e lacunas."""

    criterio: CriterioId
    nota_0_4: int = Field(ge=0, le=4, description="Escala INTEIRA — sem decimais.")
    justificativa_nota: str = Field(
        default="",
        description="1 frase explicando POR QUE a nota é essa (o que sustentou e o que faltou).",
    )
    evidencias: list[str] = Field(default_factory=list)
    lacunas: list[str] = Field(default_factory=list)
    ultimo_uso_ano: int | None = Field(
        default=None,
        description="Ano aproximado do último uso da competência (para recência).",
    )
    confianca_criterio: Confianca = Confianca.MEDIA

    @field_validator("nota_0_4", mode="before")
    @classmethod
    def _rejeitar_decimais(cls, valor: object) -> object:
        # O LLM não distingue 2,5 de 3,0 de forma estável; forçamos inteiro.
        if isinstance(valor, float) and not valor.is_integer():
            raise ValueError("A nota deve ser inteira (0-4), sem decimais.")
        return valor


class SaidaScoringLLM(BaseModel):
    """Saída completa do estágio 2 — uma nota por critério (7 no total)."""

    notas: list[NotaCriterioLLM] = Field(default_factory=list)

    def por_id(self, id_: str) -> NotaCriterioLLM | None:
        """Retorna a nota de um critério pelo id, ou None se ausente."""
        for n in self.notas:
            if n.criterio == id_:
                return n
        return None
