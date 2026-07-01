"""Testes do motor de score determinístico (Stage 5) — núcleo do produto."""

from __future__ import annotations

from app.schemas import StatusCritico, Volatilidade, VolatilidadeCompetencia
from app.triagem.score import (
    aplicar_recencia,
    calcular_score,
    pontuacao_criterio,
)
from tests.conftest import construir_notas, construir_regua


def test_pontuacao_criterio_formula() -> None:
    # Framework 6.1: peso 22, nota 3 → 22 × 3 ÷ 4 = 16,5.
    assert pontuacao_criterio(22, 3) == 16.5
    assert pontuacao_criterio(28, 4) == 28.0
    assert pontuacao_criterio(10, 0) == 0.0


def test_score_soma_dos_sete_criterios() -> None:
    regua = construir_regua()
    notas = construir_notas({c: 4 for c in ["tecnicas", "experiencia", "resultados", "complexidade", "setor", "formacao", "progressao"]})
    status = {c.id: StatusCritico.APROVADO for c in regua.criterios}
    score, criterios = calcular_score(notas, regua, status, ano_atual=2026)
    # Nota 4 em tudo → score == soma dos pesos == 100.
    assert score == 100.0
    assert len(criterios) == 7
    assert sum(c.pontuacao for c in criterios) == score


def test_recencia_alta_volatilidade_reduz_um_ponto() -> None:
    # Competência de alta volatilidade sem uso há 6 anos → -1 ponto.
    nota_aj, mod = aplicar_recencia(
        nota=4, volatilidade=Volatilidade.ALTA, ultimo_uso_ano=2020, ano_atual=2026
    )
    assert nota_aj == 3
    assert mod == -1


def test_recencia_nao_penaliza_sem_dado_nem_baixa_volatilidade() -> None:
    assert aplicar_recencia(4, Volatilidade.ALTA, None, 2026) == (4, 0)
    assert aplicar_recencia(4, Volatilidade.BAIXA, 2000, 2026) == (4, 0)


def test_recencia_aplica_em_c1_mas_nao_em_c6() -> None:
    regua = construir_regua(
        volatilidades=[VolatilidadeCompetencia(competencia="sistema PDV", volatilidade=Volatilidade.ALTA)]
    )
    # Notas 4 em tudo, mas último uso defasado (2018).
    notas = construir_notas(
        {c: 4 for c in ["tecnicas", "experiencia", "resultados", "complexidade", "setor", "formacao", "progressao"]},
        ultimo_uso_ano=2018,
    )
    status = {c.id: StatusCritico.APROVADO for c in regua.criterios}
    _, criterios = calcular_score(notas, regua, status, ano_atual=2026)
    por_id = {c.criterio: c for c in criterios}
    # tecnicas decai (alta volatilidade, defasado); formacao (formação) nunca decai.
    assert por_id["tecnicas"].recencia.modificador == -1
    assert por_id["tecnicas"].nota_0_4 == 3
    assert por_id["formacao"].recencia.modificador == 0
    assert por_id["formacao"].nota_0_4 == 4
