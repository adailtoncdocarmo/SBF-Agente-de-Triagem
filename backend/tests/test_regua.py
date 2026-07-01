"""Testes dos validators da Régua (régua de ouro: pesos congelados, 1-3 críticos)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from tests.conftest import construir_regua


def test_regua_canonica_valida() -> None:
    regua = construir_regua()
    assert sum(c.peso for c in regua.criterios) == 100
    assert sum(1 for c in regua.criterios if c.e_critico) == 2


def test_soma_pesos_diferente_de_100_falha() -> None:
    regua = construir_regua()
    # Quebra a soma alterando um peso.
    dados = regua.model_dump()
    dados["criterios"][0]["peso"] += 5
    with pytest.raises(ValidationError, match="soma dos pesos"):
        type(regua).model_validate(dados)


def test_menos_de_7_criterios_falha() -> None:
    regua = construir_regua()
    dados = regua.model_dump()
    dados["criterios"] = dados["criterios"][:6]
    with pytest.raises(ValidationError, match="7 critérios"):
        type(regua).model_validate(dados)


def test_zero_criticos_falha() -> None:
    with pytest.raises(ValidationError, match="1 a 3"):
        construir_regua(criticos=())


def test_quatro_criticos_falha() -> None:
    with pytest.raises(ValidationError, match="1 a 3"):
        construir_regua(criticos=("tecnicas", "experiencia", "resultados", "complexidade"))
