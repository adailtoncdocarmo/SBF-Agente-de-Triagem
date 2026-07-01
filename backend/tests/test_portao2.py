"""Testes do Portão 2 (Stage 4): gating de nota mínima nos críticos."""

from __future__ import annotations

from app.schemas import Confianca, StatusCritico
from app.triagem.portao2 import aplicar_portao2
from tests.conftest import construir_notas, construir_regua


def test_nota_acima_do_piso_aprova() -> None:
    regua = construir_regua(criticos=("tecnicas", "experiencia"), pisos={"tecnicas": 2, "experiencia": 2})
    notas = construir_notas({"tecnicas": 3, "experiencia": 4, "resultados": 1, "complexidade": 1, "setor": 1, "formacao": 1, "progressao": 1})
    status = aplicar_portao2(notas, regua)
    assert status["tecnicas"] == StatusCritico.APROVADO
    assert status["experiencia"] == StatusCritico.APROVADO


def test_nota_abaixo_do_piso_com_evidencia_reprova() -> None:
    regua = construir_regua(criticos=("tecnicas",), pisos={"tecnicas": 3})
    notas = construir_notas({"tecnicas": 1, "experiencia": 4, "resultados": 1, "complexidade": 1, "setor": 1, "formacao": 1, "progressao": 1})
    status = aplicar_portao2(notas, regua)
    # nota 1 < piso 3, com evidência presente e confiança alta → reprova.
    assert status["tecnicas"] == StatusCritico.REPROVADO


def test_nota_baixa_por_falta_de_evidencia_vai_para_validacao() -> None:
    regua = construir_regua(criticos=("tecnicas",), pisos={"tecnicas": 3})
    notas = construir_notas(
        {"tecnicas": 1, "experiencia": 4, "resultados": 1, "complexidade": 1, "setor": 1, "formacao": 1, "progressao": 1},
        com_evidencia=False,
        confianca=Confianca.BAIXA,
    )
    status = aplicar_portao2(notas, regua)
    # nota baixa por falta de evidência → validação (não reprova).
    assert status["tecnicas"] == StatusCritico.VALIDACAO


def test_criterio_nao_critico_e_nao_aplicavel() -> None:
    regua = construir_regua(criticos=("tecnicas",))
    notas = construir_notas({c: 2 for c in ["tecnicas", "experiencia", "resultados", "complexidade", "setor", "formacao", "progressao"]})
    status = aplicar_portao2(notas, regua)
    assert status["resultados"] == StatusCritico.NAO_APLICAVEL
    assert status["setor"] == StatusCritico.NAO_APLICAVEL
