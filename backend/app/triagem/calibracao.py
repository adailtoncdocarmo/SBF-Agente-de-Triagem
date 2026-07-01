"""Estágio 6 — Calibração do lote (Python lote-level, testável).

Não usa faixas fixas: com fórmula somativa os currículos reais se amontoam em
55-80 e a faixa não discrimina (Framework 6.5). Em vez disso, calcula o
**percentil** de cada score dentro do lote e marca **empate técnico** (|Δ| ≤ 5)
para acionar o desempate pareado. A shortlist é `percentil ≥ corte ∩ score ≥
piso absoluto`.
"""

from __future__ import annotations

from app.schemas.avaliacao import CalibracaoLote
from app.schemas.regua import Thresholds

LIMITE_EMPATE_TECNICO = 5.0


def percentil_de(valor: float, valores: list[float]) -> int:
    """Percentil de `valor` no conjunto (% de elementos ≤ valor)."""
    if not valores:
        return 0
    n_menores_ou_iguais = sum(1 for v in valores if v <= valor)
    return round(100 * n_menores_ou_iguais / len(valores))


def calibrar_lote(
    scores: dict[str, float], thresholds: Thresholds
) -> dict[str, CalibracaoLote]:
    """Calcula percentil + empate técnico de cada candidato do lote.

    Args:
        scores: mapa `id_anonimo -> score_final`.
        thresholds: limiares de corte da régua.

    Returns:
        Mapa `id_anonimo -> CalibracaoLote`.
    """
    valores = list(scores.values())
    resultado: dict[str, CalibracaoLote] = {}
    for cid, score in scores.items():
        empate = any(
            outro_id != cid and abs(score - outro) <= LIMITE_EMPATE_TECNICO
            for outro_id, outro in scores.items()
        )
        resultado[cid] = CalibracaoLote(
            percentil=percentil_de(score, valores),
            piso_absoluto=thresholds.piso_absoluto,
            empate_tecnico=empate,
        )
    return resultado


def na_shortlist(score: float, percentil: int, thresholds: Thresholds) -> bool:
    """Shortlist = acima do percentil de corte E acima do piso absoluto."""
    return percentil >= thresholds.percentil_shortlist and score >= thresholds.piso_absoluto
