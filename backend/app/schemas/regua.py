"""Schema da Régua (JobProfile) — a vaga transformada em rubrica ponderada.

A régua é a "régua de ouro" do framework: pesos, críticos e pisos são congelados
**antes** de ver qualquer currículo. O `Agente Régua` propõe; o RH edita; o app
congela. Este schema é Python-computed/editável — não é saída direta do LLM
(o LLM devolve `ReguaPropostaLLM`, que o Python normaliza para uma `Regua`).
"""

from __future__ import annotations

from pydantic import AliasChoices, BaseModel, Field, model_validator

from app.schemas.enums import (
    ROTULOS_CRITERIOS,
    CriterioId,
    Volatilidade,
)


class CriterioRegua(BaseModel):
    """Um dos 7 critérios canônicos, com peso e configuração de gating."""

    model_config = {"populate_by_name": True}

    id: CriterioId
    rotulo: str
    peso: int = Field(ge=0, le=100, description="Peso na partição; soma dos 7 = 100.")
    e_critico: bool = Field(
        default=False, description="Se marcado, passa pelo Portão 2 (gating)."
    )
    nota_minima: int = Field(
        default=2,
        ge=0,
        le=4,
        # Aceita a chave antiga `piso_senioridade` para ler réguas já salvas e
        # serializa sempre como `nota_minima` (saída explícita, sem ambiguidade).
        validation_alias=AliasChoices("nota_minima", "piso_senioridade"),
        serialization_alias="nota_minima",
        description="Nota mínima (0-4) exigida no critério decisivo (Portão 2).",
    )


class Knockout(BaseModel):
    """Requisito do Portão 1 (com justificativa job-related).

    `objetivo=True` → requisito **verificável** (CNH, registro no conselho, turno,
    idioma, localidade): quando "não atende" comprovado, elimina (zona vermelha).
    `objetivo=False` (padrão seguro) → habilidade/subjetivo: nunca elimina, vira só
    um aviso "confirmar" no card. Na dúvida, fica subjetivo.

    `tipico_no_cv=True` → requisito que normalmente aparece num currículo
    (certificação, formação, idioma): se faltar, vira aviso e rebaixa verde→amarelo.
    `tipico_no_cv=False` → requisito que raramente é escrito no CV (CNH,
    disponibilidade, localidade): a ausência NÃO penaliza (vira só "perguntar na
    entrevista"); só uma contradição explícita ("não atende") elimina.
    """

    requisito: str = Field(
        description="Rótulo CURTO (≤ ~6 palavras), sem justificativa: ex. 'CNH B', 'Inglês fluente'.",
    )
    objetivo: bool = Field(
        default=False,
        description="True só para requisitos objetivos/verificáveis (que podem eliminar).",
    )
    tipico_no_cv: bool = Field(
        default=True,
        description="True se o requisito costuma aparecer no CV; se False, ausência não penaliza.",
    )
    justificativa_job_related: str = Field(
        default="",
        description="Por que é eliminatório (legal/indispensável/risco — Framework 2.1).",
    )


class VolatilidadeCompetencia(BaseModel):
    """Classificação de volatilidade de uma competência (regra de recência)."""

    competencia: str
    volatilidade: Volatilidade


class Thresholds(BaseModel):
    """Cortes de decisão da vaga, em **nota absoluta 0-100**.

    A zona vem direto da nota: `nota ≥ corte_verde` → verde; `≥ corte_amarelo` →
    amarelo; abaixo → vermelho. O preset "Rigor" controla esses dois cortes.
    Os campos `percentil_shortlist`/`piso_absoluto` são legados (réguas antigas)
    e não decidem mais a zona.
    """

    corte_verde: int = Field(default=60, ge=0, le=100, description="Nota mínima para 'Promissor' (verde).")
    corte_amarelo: int = Field(default=35, ge=0, le=100, description="Nota mínima para 'Revisar' (amarelo).")
    alvo_auto_decisao: float = Field(default=0.65, ge=0.0, le=1.0)
    # Legados — mantidos só para ler réguas antigas (migração automática abaixo).
    percentil_shortlist: int = Field(default=80, ge=0, le=100)
    piso_absoluto: int = Field(default=55, ge=0, le=100)

    @model_validator(mode="after")
    def _coerencia_cortes(self) -> "Thresholds":
        if self.corte_amarelo > self.corte_verde:
            self.corte_amarelo = self.corte_verde
        return self


class Regua(BaseModel):
    """A vaga como rubrica congelável: 7 critérios + knockouts + thresholds."""

    criterios: list[CriterioRegua]
    knockouts: list[Knockout] = Field(default_factory=list)
    volatilidades: list[VolatilidadeCompetencia] = Field(default_factory=list)
    thresholds: Thresholds = Field(default_factory=Thresholds)
    congelada: bool = False

    @model_validator(mode="after")
    def _validar_regua(self) -> "Regua":
        ids = [c.id for c in self.criterios]
        if len(ids) != 7 or set(ids) != set(ROTULOS_CRITERIOS):
            raise ValueError("A régua deve ter exatamente os 7 critérios canônicos.")
        soma = sum(c.peso for c in self.criterios)
        if soma != 100:
            raise ValueError(f"A soma dos pesos deve ser 100 (recebido: {soma}).")
        n_criticos = sum(1 for c in self.criterios if c.e_critico)
        if not 1 <= n_criticos <= 3:
            raise ValueError(
                f"Marque de 1 a 3 critérios como críticos (recebido: {n_criticos})."
            )
        return self

    def criterio(self, id_: str) -> CriterioRegua:
        """Retorna o critério pelo id (ex.: 'tecnicas')."""
        for c in self.criterios:
            if c.id == id_:
                return c
        raise KeyError(f"Critério {id_} não encontrado na régua.")
