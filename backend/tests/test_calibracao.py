"""Testes da calibração do lote (Stage 6): percentil, empate técnico, shortlist."""

from __future__ import annotations

from app.schemas import Thresholds
from app.triagem.calibracao import calibrar_lote, na_shortlist, percentil_de


def test_percentil_de() -> None:
    valores = [10.0, 20.0, 30.0, 40.0, 50.0]
    assert percentil_de(50.0, valores) == 100
    assert percentil_de(10.0, valores) == 20
    assert percentil_de(30.0, valores) == 60
    assert percentil_de(99.0, []) == 0


def test_empate_tecnico_marca_diferenca_pequena() -> None:
    scores = {"A": 80.0, "B": 78.0, "C": 50.0}
    calib = calibrar_lote(scores, Thresholds())
    # A e B diferem por 2 (≤5) → empate técnico; C está isolado.
    assert calib["A"].empate_tecnico is True
    assert calib["B"].empate_tecnico is True
    assert calib["C"].empate_tecnico is False


def test_na_shortlist_exige_percentil_e_piso() -> None:
    th = Thresholds(percentil_shortlist=80, piso_absoluto=55)
    assert na_shortlist(score=70.0, percentil=85, thresholds=th) is True
    # Percentil alto mas score abaixo do piso → fora.
    assert na_shortlist(score=50.0, percentil=90, thresholds=th) is False
    # Score alto mas percentil abaixo do corte → fora.
    assert na_shortlist(score=70.0, percentil=70, thresholds=th) is False
