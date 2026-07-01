"""Estágio 4 — Portão 2: gating de nota mínima nos críticos (Python, testável).

Depois de pontuar (estágio 2), antes de o total valer, cada critério **crítico**
precisa atingir a `nota_minima` definida na régua. A distinção essencial
(que conecta o Ajuste 1 ao 2):
    - nota ≥ nota mínima                       → aprovado
    - nota < nota mínima COM evidência presente → reprovado (sai do ranking)
    - nota baixa por FALTA de evidência        → validação (vai para o humano)

Opera sobre as notas brutas do LLM (sinal de evidência). A recência (que só
ajusta a contribuição ao score) é aplicada depois, em `score.py`.
"""

from __future__ import annotations

from app.schemas.enums import Confianca, StatusCritico
from app.schemas.llm_scoring import SaidaScoringLLM
from app.schemas.regua import Regua


def aplicar_portao2(notas: SaidaScoringLLM, regua: Regua) -> dict[str, StatusCritico]:
    """Classifica cada critério crítico em aprovado / reprovado / validação.

    Returns:
        Mapa `id_criterio -> StatusCritico` para os 7 critérios (os não-críticos
        recebem `NAO_APLICAVEL`).
    """
    resultado: dict[str, StatusCritico] = {}
    for criterio in regua.criterios:
        if not criterio.e_critico:
            resultado[criterio.id] = StatusCritico.NAO_APLICAVEL
            continue

        nota = notas.por_id(criterio.id)
        if nota is None:
            # Sem dado nenhum → falta de evidência → validação (não reprova).
            resultado[criterio.id] = StatusCritico.VALIDACAO
            continue

        if nota.nota_0_4 >= criterio.nota_minima:
            resultado[criterio.id] = StatusCritico.APROVADO
        else:
            # Nota abaixo do piso: reprova só se há evidência presente e confiança
            # suficiente; senão é falta de evidência → validação (Framework 6.3).
            tem_evidencia = bool(nota.evidencias) and nota.confianca_criterio != Confianca.BAIXA
            resultado[criterio.id] = (
                StatusCritico.REPROVADO if tem_evidencia else StatusCritico.VALIDACAO
            )
    return resultado
