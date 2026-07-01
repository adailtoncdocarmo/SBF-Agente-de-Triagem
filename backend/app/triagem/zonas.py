"""Estágio 8 — Classificação nas três zonas (Python, simples e previsível).

Modelo de decisão (revisado para ser intuitivo ao RH):
  A zona vem DIRETO da **nota 0-100** caindo numa de três faixas, controladas
  pelo preset de Rigor:
    nota ≥ corte_verde   → ENTRA  (Promissor)
    nota ≥ corte_amarelo → AVALIAR (Revisar)
    abaixo               → CAI    (Fora do perfil)

  O ÚNICO override que vira vermelho ignorando a nota é um **requisito objetivo
  e verificável** comprovadamente NÃO atendido (ex.: vaga de motorista sem CNH).

  Todo o resto (requisito não comprovado, decisivo em validação/reprovado,
  confiança baixa, flag alta) vira **aviso transparente** ("ressalva") no card e,
  no máximo, **rebaixa um VERDE para AMARELO com o motivo escrito** — nunca em
  silêncio, nunca empurra amarelo→vermelho, nunca promove. Se um requisito
  eliminatório "Esperado no CV" não aparece no currículo, rebaixa (pede
  confirmação); se for "Perguntar depois", só vira lembrete para a entrevista.

  O percentil continua calculado (ranking/desempate), mas NÃO decide a zona —
  acabou o paradoxo "nota alta mas não fica verde".

`taxa_auto_decisao = (entra + cai) / total` segue como a métrica-produto.
"""

from __future__ import annotations

from app.schemas.avaliacao import Avaliacao
from app.schemas.enums import (
    Confianca,
    EstadoKnockout,
    Recomendacao,
    Severidade,
    StatusCritico,
    ZonaDecisao,
)
from app.schemas.llm_portao1 import KnockoutAvaliadoLLM
from app.schemas.regua import Regua, Thresholds

# Só flags ALTA/CRÍTICA viram ressalva (rebaixam verde). Flags MÉDIA são apenas
# "pontos de atenção" exibidos no card, sem rebaixar.
_SEVERIDADES_BLOQUEANTES = {Severidade.ALTA, Severidade.CRITICA}


def aplicar_flags_knockout(portao_1: list[KnockoutAvaliadoLLM], regua: Regua) -> None:
    """Casa cada knockout avaliado com o da régua e fixa requisito/objetivo/tipico_no_cv.

    A IA frequentemente devolve o `requisito` com a justificativa anexada (porque o
    enviamos assim no prompt), então casar por **igualdade exata** falha e os flags
    `objetivo`/`tipico_no_cv` da régua nunca chegavam ao candidato (caíam no default)
    — por isso marcar "Eliminatório" não surtia efeito. Aqui casamos por prefixo/
    contém e normalizamos o `requisito` para o texto limpo da régua (melhora o card).

    Deve ser chamado tanto na avaliação por IA (orquestrador) quanto no reprocesso
    determinístico (mudar "Eliminatório"/"Esperado no CV" reflete sem reextração).
    """
    for kc in portao_1:
        alvo = next(
            (
                k
                for k in regua.knockouts
                if kc.requisito == k.requisito
                or (k.requisito and kc.requisito.startswith(k.requisito))
                or (k.requisito and k.requisito in kc.requisito)
            ),
            None,
        )
        if alvo is not None:
            kc.requisito = alvo.requisito
            kc.objetivo = alvo.objetivo
            kc.tipico_no_cv = alvo.tipico_no_cv


def _para_recomendacao(zona: ZonaDecisao) -> Recomendacao:
    return {
        ZonaDecisao.ENTRA: Recomendacao.AVANCAR,
        ZonaDecisao.AVALIAR: Recomendacao.AVALIAR,
        ZonaDecisao.CAI: Recomendacao.NAO_AVANCAR,
    }[zona]


def montar_ressalvas(avaliacao: Avaliacao) -> tuple[list[str], bool]:
    """Reúne os avisos do candidato e diz se eles rebaixam um verde.

    Para um requisito eliminatório que o CV não comprova (NÃO EVIDENCIADO), quem
    decide se rebaixa é o seletor do RH "Esperado no CV / Perguntar depois"
    (`tipico_no_cv`), não o flag `objetivo`. O `objetivo` só governa o override
    duro (vermelho) de um "não atende" verificável, em `classificar_zona`.

    Returns:
        `(selos, rebaixa)` — `selos` são os textos exibidos no card; `rebaixa` é
        True se houver algum aviso que justifique mover um VERDE para AMARELO.
    """
    selos: list[str] = []
    rebaixa = False

    def _curto(texto: str, n: int = 70) -> str:
        texto = texto.strip()
        return texto if len(texto) <= n else texto[: n - 1].rstrip() + "…"

    for k in avaliacao.portao_1:
        if k.estado == EstadoKnockout.ATENDE:
            continue
        if k.estado == EstadoKnockout.NAO_EVIDENCIADO:
            # O CV é OMISSO sobre o requisito. Quem decide se isso penaliza é o
            # seletor do RH "Esperado no CV / Perguntar depois" (`tipico_no_cv`) —
            # NÃO o flag `objetivo` (inferido pela IA e nem sempre correto). Era esse
            # acoplamento que fazia "Eliminatório + Esperado no CV" não surtir efeito.
            if k.tipico_no_cv:
                # "Esperado no CV": normalmente apareceria e não apareceu → ausência
                # suspeita; pede confirmação e rebaixa (verde→amarelo).
                selos.append(f"Confirmar requisito obrigatório: {_curto(k.requisito)}")
                rebaixa = True
            else:
                # "Perguntar depois": raramente escrito no CV (CNH, disponibilidade):
                # a ausência NÃO penaliza — vira só um lembrete para a entrevista.
                selos.append(f"Verificar na entrevista: {_curto(k.requisito)}")
        elif k.objetivo:
            # NÃO ATENDE objetivo e verificável → override duro (vermelho) em
            # classificar_zona; aqui só registra o selo informativo.
            selos.append(f"Requisito obrigatório não atendido: {_curto(k.requisito)}")
        else:
            # NÃO ATENDE subjetivo (habilidade): só lembrete, não elimina nem rebaixa.
            selos.append(f"Confirmar: {_curto(k.requisito)}")

    for c in avaliacao.criterios:
        if not c.critico:
            continue
        if c.status_critico == StatusCritico.VALIDACAO:
            selos.append(f"Confirmar critério decisivo: {c.rotulo}")
            rebaixa = True
        elif c.status_critico == StatusCritico.REPROVADO:
            selos.append(f"Abaixo do mínimo em: {c.rotulo}")
            rebaixa = True

    if avaliacao.confianca == Confianca.BAIXA:
        selos.append("Avaliação incerta — revisar")
        rebaixa = True

    for f in avaliacao.flags.risco:
        if f.severidade in _SEVERIDADES_BLOQUEANTES:
            selos.append(f"Risco: {f.descricao[:80]}")
            rebaixa = True

    return selos, rebaixa


def classificar_zona(
    avaliacao: Avaliacao, thresholds: Thresholds
) -> tuple[ZonaDecisao, Recomendacao, bool, str, list[str]]:
    """Classifica um candidato pela nota absoluta + ressalvas.

    Returns:
        `(zona, recomendacao, rejeicao_automatica_permitida, motivo, ressalvas)`.
    """
    score = avaliacao.score_final
    selos, rebaixa = montar_ressalvas(avaliacao)

    # 0) Override duro: requisito OBJETIVO comprovadamente não atendido → vermelho.
    if any(
        k.estado == EstadoKnockout.NAO_ATENDE and k.objetivo for k in avaliacao.portao_1
    ):
        zona = ZonaDecisao.CAI
        return (
            zona,
            _para_recomendacao(zona),
            True,
            "Requisito obrigatório objetivo não atendido.",
            selos,
        )

    # 1) Faixa por nota absoluta.
    if score >= thresholds.corte_verde:
        base = ZonaDecisao.ENTRA
    elif score >= thresholds.corte_amarelo:
        base = ZonaDecisao.AVALIAR
    else:
        base = ZonaDecisao.CAI

    # 2) Rebaixamento de no máximo 1 degrau: só VERDE→AMARELO, e sempre com motivo.
    if base == ZonaDecisao.ENTRA and rebaixa:
        zona = ZonaDecisao.AVALIAR
        motivo = "Promissor, mas validar: " + "; ".join(selos)
        return zona, _para_recomendacao(zona), False, motivo, selos

    motivo = {
        ZonaDecisao.ENTRA: "Acima do corte de aprovação da vaga.",
        ZonaDecisao.AVALIAR: "Na faixa de revisão humana.",
        ZonaDecisao.CAI: "Abaixo da nota mínima da vaga.",
    }[base]
    rejeicao = base in (ZonaDecisao.ENTRA, ZonaDecisao.CAI)
    return base, _para_recomendacao(base), rejeicao, motivo, selos


def calcular_taxa_auto_decisao(zonas: list[ZonaDecisao]) -> float:
    """`(entra + cai) / total` — quanto a IA resolve sozinha com segurança."""
    if not zonas:
        return 0.0
    auto = sum(1 for z in zonas if z in (ZonaDecisao.ENTRA, ZonaDecisao.CAI))
    return round(auto / len(zonas), 4)
