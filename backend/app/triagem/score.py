"""Estágio 5 — Motor de score determinístico (Python, núcleo testável).

A nota **nunca** sai da IA: aqui o Python aplica a fórmula aprovada
(`peso × nota ÷ 4`), o fator de recência por volatilidade (Framework Parte 3) e
soma os 7 critérios (0-100). Mesmos sinais ⇒ sempre o mesmo score.

Decisão de projeto: a recência só ajusta a **contribuição ao score** dos
critérios de competências técnicas e experiência; não se aplica à formação. O
Portão 2 (gating) usa as notas brutas — recência é sobre defasagem, gating é
sobre evidência. Pequena divergência deliberada e documentada.
"""

from __future__ import annotations

from app.schemas.avaliacao import CriterioAvaliado, RecenciaCalculada
from app.schemas.enums import Confianca, StatusCritico, Volatilidade
from app.schemas.llm_scoring import SaidaScoringLLM
from app.schemas.regua import Regua

# Limiares de defasagem (Framework Parte 3): alta ~24-36 meses; média ~5 anos.
ANOS_DECAI_ALTA = 3
ANOS_DECAI_MEDIA = 5

# Recência só incide sobre competências técnicas e experiência.
CRITERIOS_COM_RECENCIA = {"tecnicas", "experiencia"}

_ORDEM_VOLATILIDADE = {Volatilidade.ALTA: 3, Volatilidade.MEDIA: 2, Volatilidade.BAIXA: 1}


def pontuacao_criterio(peso: int, nota: int) -> float:
    """Fórmula aprovada do critério: `peso × nota ÷ 4`."""
    return round(peso * nota / 4, 2)


def aplicar_recencia(
    nota: int,
    volatilidade: Volatilidade,
    ultimo_uso_ano: int | None,
    ano_atual: int,
) -> tuple[int, int]:
    """Aplica o fator de recência. Retorna `(nota_ajustada, modificador)`.

    Não penaliza por falta de dado (ultimo_uso desconhecido → modificador 0) nem
    competências de baixa volatilidade. Piso 0.
    """
    if volatilidade == Volatilidade.BAIXA or ultimo_uso_ano is None:
        return nota, 0
    anos_sem_uso = ano_atual - ultimo_uso_ano
    decai = (volatilidade == Volatilidade.ALTA and anos_sem_uso >= ANOS_DECAI_ALTA) or (
        volatilidade == Volatilidade.MEDIA and anos_sem_uso >= ANOS_DECAI_MEDIA
    )
    if decai:
        return max(0, nota - 1), -1
    return nota, 0


def volatilidade_dominante(regua: Regua) -> Volatilidade:
    """Maior volatilidade entre as competências da régua (decay conservador)."""
    if not regua.volatilidades:
        return Volatilidade.BAIXA
    return max(
        (v.volatilidade for v in regua.volatilidades),
        key=lambda vol: _ORDEM_VOLATILIDADE[vol],
    )


def calcular_score(
    notas: SaidaScoringLLM,
    regua: Regua,
    status_criticos: dict[str, StatusCritico],
    ano_atual: int,
) -> tuple[float, list[CriterioAvaliado]]:
    """Calcula o score final (0-100) e o detalhamento rastreável por critério."""
    vol_dom = volatilidade_dominante(regua)
    avaliados: list[CriterioAvaliado] = []

    for criterio in regua.criterios:
        nota_llm = notas.por_id(criterio.id)
        nota_bruta = nota_llm.nota_0_4 if nota_llm else 0
        ultimo_uso = nota_llm.ultimo_uso_ano if nota_llm else None
        confianca = nota_llm.confianca_criterio if nota_llm else Confianca.BAIXA

        if criterio.id in CRITERIOS_COM_RECENCIA:
            nota_aj, modificador = aplicar_recencia(nota_bruta, vol_dom, ultimo_uso, ano_atual)
            recencia = RecenciaCalculada(
                volatilidade=vol_dom,
                ultimo_uso=str(ultimo_uso) if ultimo_uso else None,
                modificador=modificador,
            )
        else:
            nota_aj = nota_bruta
            recencia = RecenciaCalculada(
                volatilidade=Volatilidade.BAIXA,
                ultimo_uso=str(ultimo_uso) if ultimo_uso else None,
                modificador=0,
            )

        avaliados.append(
            CriterioAvaliado(
                criterio=criterio.id,
                rotulo=criterio.rotulo,
                critico=criterio.e_critico,
                peso=criterio.peso,
                nota_0_4=nota_aj,
                nota_minima=criterio.nota_minima,
                status_critico=status_criticos.get(criterio.id, StatusCritico.NAO_APLICAVEL),
                confianca_criterio=confianca,
                recencia=recencia,
                pontuacao=pontuacao_criterio(criterio.peso, nota_aj),
                justificativa_nota=nota_llm.justificativa_nota if nota_llm else "",
                evidencias=list(nota_llm.evidencias) if nota_llm else [],
                lacunas=list(nota_llm.lacunas) if nota_llm else [],
            )
        )

    score_final = round(sum(c.pontuacao for c in avaliados), 2)
    return score_final, avaliados
