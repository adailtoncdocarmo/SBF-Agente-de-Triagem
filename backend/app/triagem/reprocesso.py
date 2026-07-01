"""Reprocesso determinístico da vaga ao recalibrar a régua (sem custo de IA).

Quando o RH só muda **pesos/críticos/pisos/thresholds/volatilidades**, não é
preciso reextrair sinais com a IA: as notas brutas 0-4 já estão persistidas em
cada `Avaliacao`. O Python reconstrói a saída de scoring a partir delas, re-roda
o Portão 2 + o motor de score com a régua nova e recalibra/rezoneia a população
inteira da vaga — instantâneo e auditável.

Mudanças que exigem reextração com IA (rótulos de critério ou knockouts) seguem
por outro caminho (re-enfileirar os lotes); ver `precisa_reextrair`.
"""

from __future__ import annotations

import datetime as _dt
import logging

from sqlalchemy import select

from app.database import SessionLocal
from app.models_db import Candidato, Lote
from app.schemas.avaliacao import Avaliacao
from app.schemas.enums import (
    EstagioCandidato,
    StatusCandidato,
    StatusLote,
)
from app.schemas.llm_scoring import NotaCriterioLLM, SaidaScoringLLM
from app.schemas.regua import Regua, Thresholds
from app.triagem.calibracao import calibrar_lote
from app.triagem.portao2 import aplicar_portao2
from app.triagem.score import calcular_score
from app.triagem.zonas import aplicar_flags_knockout, classificar_zona

logger = logging.getLogger("triagem.reprocesso")

_ANO_ATUAL = _dt.date.today().year


def precisa_reextrair(antiga: Regua, nova: Regua) -> bool:
    """True se a mudança da régua exige reextração com IA (não só recálculo).

    Reextrair só é necessário quando muda o que a IA interpreta: o **rótulo** de
    um critério (muda o que ela pontua) ou os **knockouts** (muda o Portão 1).
    Pesos, críticos, pisos, thresholds e volatilidades são puro Python.
    """
    rotulos_antigos = {c.id: c.rotulo for c in antiga.criterios}
    rotulos_novos = {c.id: c.rotulo for c in nova.criterios}
    if rotulos_antigos != rotulos_novos:
        return True
    ko_antigos = [(k.requisito, k.justificativa_job_related) for k in antiga.knockouts]
    ko_novos = [(k.requisito, k.justificativa_job_related) for k in nova.knockouts]
    return ko_antigos != ko_novos


def _reconstruir_scoring(avaliacao: Avaliacao) -> SaidaScoringLLM:
    """Recupera a saída de scoring da IA (notas brutas 0-4) de uma `Avaliacao`.

    A nota persistida (`nota_0_4`) já vem ajustada por recência (modificador 0 ou
    -1); a bruta é `nota_0_4 - modificador`. O `calcular_score` reaplica a
    recência com a régua nova, então devolvemos a bruta.
    """
    notas: list[NotaCriterioLLM] = []
    for c in avaliacao.criterios:
        nota_bruta = c.nota_0_4 - c.recencia.modificador
        nota_bruta = max(0, min(4, nota_bruta))
        ultimo = c.recencia.ultimo_uso
        ultimo_ano = int(ultimo) if ultimo and ultimo.isdigit() else None
        notas.append(
            NotaCriterioLLM(
                criterio=c.criterio,
                nota_0_4=nota_bruta,
                justificativa_nota=c.justificativa_nota,
                evidencias=list(c.evidencias),
                lacunas=list(c.lacunas),
                ultimo_uso_ano=ultimo_ano,
                confianca_criterio=c.confianca_criterio,
            )
        )
    return SaidaScoringLLM(notas=notas)


def reprocessar_vaga_deterministico(vaga_id: int, regua: Regua) -> int:
    """Recalcula score + zonas de toda a vaga com a régua nova, sem IA.

    Returns:
        Quantidade de candidatos reprocessados.
    """
    with SessionLocal() as sessao:
        candidatos = list(
            sessao.scalars(
                select(Candidato)
                .join(Lote, Candidato.lote_id == Lote.id)
                .where(
                    Lote.vaga_id == vaga_id,
                    Candidato.status == StatusCandidato.CONCLUIDO.value,
                )
            )
        )
        dados: list[tuple[int, str, Avaliacao]] = []
        for c in candidatos:
            if c.avaliacao is None:
                continue
            av = Avaliacao.model_validate(c.avaliacao.avaliacao_json)
            # Reaplica os flags de knockout da régua nova ao Portão 1 já avaliado —
            # assim mudar "Eliminatório"/"Esperado no CV" de um requisito existente
            # reflete na zona sem precisar reextrair com IA.
            aplicar_flags_knockout(av.portao_1, regua)
            scoring = _reconstruir_scoring(av)
            status_criticos = aplicar_portao2(scoring, regua)
            score_final, criterios = calcular_score(
                scoring, regua, status_criticos, _ANO_ATUAL
            )
            av.score_final = score_final
            av.criterios = criterios
            dados.append((c.id, c.id_anonimo, av))

        if not dados:
            return 0

        # Recalibra (percentil) + rezoneia sobre o pool inteiro com a régua nova.
        scores = {id_anon: av.score_final for _, id_anon, av in dados}
        calib = calibrar_lote(scores, regua.thresholds)
        for _, id_anon, av in dados:
            av.calibracao_lote = calib[id_anon]
        for _, _id, av in dados:
            zona, recomendacao, rejeicao, motivo, ressalvas = classificar_zona(av, regua.thresholds)
            av.zona_decisao = zona
            av.recomendacao = recomendacao
            av.rejeicao_automatica_permitida = rejeicao
            av.motivo_zona = motivo
            av.ressalvas = ressalvas

        for cid, _id, av in dados:
            candidato = sessao.get(Candidato, cid)
            if candidato is None:
                continue
            candidato.score_final = av.score_final
            candidato.zona = av.zona_decisao.value if av.zona_decisao else None
            orm = candidato.avaliacao
            if orm is not None:
                orm.avaliacao_json = av.model_dump(mode="json")
                orm.score_final = av.score_final
                orm.zona = av.zona_decisao.value if av.zona_decisao else None
        sessao.commit()

    logger.info("Vaga %s reprocessada (determinístico): %s CVs.", vaga_id, len(dados))
    return len(dados)


def aplicar_thresholds_a_todas_vagas(novos: dict) -> int:
    """Aplica novos cortes (percentil/piso/alvo) a TODAS as vagas e recalcula.

    É o caminho determinístico do ajuste global de "Parâmetros de avaliação":
    grava os thresholds na régua de cada vaga e reprocessa sem IA (recalibra o
    percentil sobre o pool e reaplica as zonas). Retorna quantas vagas tinham
    candidatos e foram recalculadas.
    """
    from app.models_db import Vaga

    with SessionLocal() as sessao:
        vagas = list(sessao.scalars(select(Vaga)))
        pendentes: list[tuple[int, Regua]] = []
        for vaga in vagas:
            regua = Regua.model_validate(vaga.regua_json)
            th = regua.thresholds
            if novos.get("corte_verde") is not None:
                th.corte_verde = int(novos["corte_verde"])
            if novos.get("corte_amarelo") is not None:
                th.corte_amarelo = int(novos["corte_amarelo"])
            if novos.get("alvo_auto_decisao") is not None:
                th.alvo_auto_decisao = float(novos["alvo_auto_decisao"])
            # revalida coerência (corte_amarelo <= corte_verde)
            regua.thresholds = Thresholds.model_validate(th.model_dump())
            vaga.regua_json = regua.model_dump(mode="json")
            pendentes.append((vaga.id, regua))
        sessao.commit()

    recalculadas = 0
    for vaga_id, regua in pendentes:
        if reprocessar_vaga_deterministico(vaga_id, regua) > 0:
            recalculadas += 1
    logger.info("Thresholds globais aplicados a %s vaga(s).", recalculadas)
    return recalculadas


def reenfileirar_falhas_da_vaga(vaga_id: int) -> tuple[int, list[int]]:
    """Recoloca na fila SÓ os CVs que falharam (status erro) da vaga.

    Os concluídos são preservados (o orquestrador os pula). Útil para recuperar
    CVs derrubados por instabilidade momentânea da API. Retorna
    `(qtd_candidatos, lote_ids)` para o router enfileirar e o front acompanhar.
    """
    with SessionLocal() as sessao:
        candidatos = list(
            sessao.scalars(
                select(Candidato)
                .join(Lote, Candidato.lote_id == Lote.id)
                .where(
                    Lote.vaga_id == vaga_id,
                    Candidato.status == StatusCandidato.ERRO.value,
                )
            )
        )
        lote_ids: set[int] = set()
        for c in candidatos:
            c.status = StatusCandidato.ENFILEIRADO.value
            c.estagio_atual = EstagioCandidato.CEGAMENTO.value
            c.erro = None
            c.zona = None
            c.score_final = None
            lote_ids.add(c.lote_id)
        for lid in lote_ids:
            lote = sessao.get(Lote, lid)
            if lote is not None:
                lote.status = StatusLote.ENFILEIRADO.value
        sessao.commit()
    logger.info(
        "Vaga %s: reenfileirados %s CV(s) que falharam em %s lote(s).",
        vaga_id, len(candidatos), len(lote_ids),
    )
    return len(candidatos), sorted(lote_ids)


def resetar_vaga_para_reextracao(vaga_id: int) -> list[int]:
    """Reseta os CVs da vaga para reextração com IA e devolve os lotes a reenfileirar.

    Volta cada candidato (concluído, em espera ou com erro) para `enfileirado` e
    cada lote para `enfileirado`. O orquestrador então reexecuta os estágios 1-5
    (a `Avaliacao` antiga é sobrescrita no upsert) e recalibra a vaga ao final.
    """
    with SessionLocal() as sessao:
        lotes = list(
            sessao.scalars(select(Lote).where(Lote.vaga_id == vaga_id))
        )
        candidatos = list(
            sessao.scalars(
                select(Candidato)
                .join(Lote, Candidato.lote_id == Lote.id)
                .where(Lote.vaga_id == vaga_id)
            )
        )
        for c in candidatos:
            c.status = StatusCandidato.ENFILEIRADO.value
            c.estagio_atual = EstagioCandidato.CEGAMENTO.value
            c.zona = None
            c.score_final = None
            c.erro = None
        lote_ids: list[int] = []
        for lote in lotes:
            lote.status = StatusLote.ENFILEIRADO.value
            lote_ids.append(lote.id)
        sessao.commit()
    logger.info("Vaga %s resetada para reextração com IA: %s lote(s).", vaga_id, len(lote_ids))
    return lote_ids
