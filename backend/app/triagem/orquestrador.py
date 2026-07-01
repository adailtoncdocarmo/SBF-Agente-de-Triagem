"""Orquestrador — encadeia os estágios per-CV e lote-level (Framework v3).

Decisão de LGPD: o **cegamento (Stage 0) roda no upload** (router), nunca no
worker — assim a PII nunca chega ao banco. O orquestrador parte do
`texto_cegado` já persistido.

Fluxo:
    per-CV  (Stage 1-5): Portão 1 ‖ scoring ‖ flags (LLM) → Portão 2 → score (Python)
    lote    (Stage 6-9): calibração → desempate (empates) → zonas → contagens + notificação

Nota sobre a numeração: os números "Stage/Estágio N" das docstrings seguem a
ordem de IMPLEMENTAÇÃO (0-based), não os 10 passos (1-based) do Framework v3.
No bloco per-CV, Portão 1 / scoring / flags rodam em PARALELO (não sequencial);
no bloco de lote, zonas (8) é calculada ANTES do desempate (7), que só dá um
nudge de ordenação nos empates do topo — por isso a ordem real é 6 → 8 → 7.

Idempotente/retomável: cada CV concluído vira `aguardando_lote` com avaliação
parcial persistida; ao reprocessar o lote, CVs prontos são pulados. Falha em um
CV marca `status=erro` e **não derruba o lote** (erro nunca silenciado).
"""

from __future__ import annotations

import asyncio
import datetime as _dt
import logging

from sqlalchemy import func, select

from app import configuracao_runtime as cfg_rt
from app.database import SessionLocal
from app.models_db import Avaliacao as AvaliacaoORM
from app.models_db import Candidato, Lote, Notificacao, RegistroCusto, Vaga
from app.schemas.avaliacao import Avaliacao, Flags
from app.schemas.enums import (
    EstagioCandidato,
    StatusCandidato,
    StatusLote,
    ZonaDecisao,
)
from app.schemas.regua import Regua
from app.triagem import estagios
from app.triagem.calibracao import calibrar_lote
from app.triagem.cliente_llm import ClienteLLM
from app.triagem.ficha import chave_ordenacao
from app.triagem.portao2 import aplicar_portao2
from app.triagem.score import calcular_score
from app.triagem.zonas import aplicar_flags_knockout, calcular_taxa_auto_decisao, classificar_zona

logger = logging.getLogger("triagem.orquestrador")

_ANO_ATUAL = _dt.date.today().year
# Limite de candidatos do topo considerados no desempate pareado (controle de custo).
_TOPO_DESEMPATE = 8


def _registrador_custo(info: dict[str, object]) -> None:
    """Persiste um RegistroCusto (sessão curta — WAL cuida da concorrência)."""
    try:
        with SessionLocal() as sessao:
            sessao.add(RegistroCusto(**info))
            sessao.commit()
    except Exception:  # telemetria nunca derruba a triagem
        logger.exception("Falha ao registrar custo (ignorado).")


async def processar_lote(lote_id: int) -> None:
    """Processa um lote inteiro: per-CV → lote-level → notificação."""
    with SessionLocal() as sessao:
        lote = sessao.get(Lote, lote_id)
        if lote is None:
            logger.warning("Lote %s não encontrado — ignorando.", lote_id)
            return
        vaga = sessao.get(Vaga, lote.vaga_id)
        regua = Regua.model_validate(vaga.regua_json)
        vaga_titulo = vaga.titulo
        lote.status = StatusLote.PROCESSANDO.value
        sessao.commit()
        candidato_ids = [
            c.id for c in sessao.scalars(select(Candidato).where(Candidato.lote_id == lote_id))
        ]

    cliente = ClienteLLM(ao_registrar_custo=_registrador_custo)
    semaforo = asyncio.Semaphore(cfg_rt.obter_concorrencia())

    async def _com_semaforo(cid: int) -> None:
        async with semaforo:
            await _processar_candidato(cid, regua, vaga_titulo, cliente, lote_id)

    await asyncio.gather(*(_com_semaforo(cid) for cid in candidato_ids))

    await _finalizar_lote(lote_id, vaga_titulo, regua, cliente)


async def _processar_candidato(
    candidato_id: int,
    regua: Regua,
    vaga_titulo: str,
    cliente: ClienteLLM,
    lote_id: int,
) -> None:
    """Estágios 1-5 de um CV. Isola erros para não derrubar o lote."""
    with SessionLocal() as sessao:
        candidato = sessao.get(Candidato, candidato_id)
        if candidato is None:
            return
        # Retomada: pula CVs já prontos.
        if candidato.status in (
            StatusCandidato.AGUARDANDO_LOTE.value,
            StatusCandidato.CONCLUIDO.value,
        ):
            return
        candidato.status = StatusCandidato.PROCESSANDO.value
        texto = candidato.texto_cegado or ""
        id_anonimo = candidato.id_anonimo
        sessao.commit()

    try:
        portao1, scoring, flags = await asyncio.gather(
            estagios.avaliar_portao1(
                cliente, texto_cegado=texto, regua=regua, lote_id=lote_id, candidato_id=candidato_id,
            ),
            estagios.avaliar_criterios(
                cliente, texto_cegado=texto, regua=regua, lote_id=lote_id, candidato_id=candidato_id,
            ),
            estagios.avaliar_flags(
                cliente, texto_cegado=texto, lote_id=lote_id, candidato_id=candidato_id,
            ),
        )

        status_criticos = aplicar_portao2(scoring, regua)
        score_final, criterios = calcular_score(scoring, regua, status_criticos, _ANO_ATUAL)

        # Casa os knockouts avaliados com a régua: fixa o texto limpo e os flags
        # `objetivo` (só esses eliminam) e `tipico_no_cv` (ausência penaliza ou não).
        # A IA não decide isso — vem da régua. Casamento tolerante à justificativa.
        aplicar_flags_knockout(portao1.knockouts, regua)

        avaliacao = Avaliacao(
            candidato=id_anonimo,
            vaga=vaga_titulo,
            portao_1=portao1.knockouts,
            criterios=criterios,
            score_final=score_final,
            flags=Flags(risco=flags.risco, clareza=flags.clareza),
            confianca=flags.clareza.confianca_avaliacao,
        )

        with SessionLocal() as sessao:
            candidato = sessao.get(Candidato, candidato_id)
            candidato.score_final = score_final
            candidato.status = StatusCandidato.AGUARDANDO_LOTE.value
            candidato.estagio_atual = EstagioCandidato.SCORE.value
            candidato.erro = None
            _salvar_avaliacao(sessao, candidato_id, avaliacao)
            sessao.commit()

    except Exception as exc:  # erro nunca silenciado; isola o CV
        logger.exception("Erro ao processar candidato %s", candidato_id)
        with SessionLocal() as sessao:
            candidato = sessao.get(Candidato, candidato_id)
            if candidato is not None:
                candidato.status = StatusCandidato.ERRO.value
                candidato.erro = str(exc)[:500]
                sessao.commit()


async def _finalizar_lote(
    lote_id: int, vaga_titulo: str, regua: Regua, cliente: ClienteLLM
) -> None:
    """Estágios 6-9: recalibra a POPULAÇÃO INTEIRA da vaga (pool acumulado).

    Os CVs deste lote (`aguardando_lote`) entram no pool junto com os já
    `concluido` de lotes anteriores — assim subir um 2º lote reposiciona o 1º.
    """
    with SessionLocal() as sessao:
        lote = sessao.get(Lote, lote_id)
        vaga_id = lote.vaga_id if lote else None
        n_erros = len(
            list(
                sessao.scalars(
                    select(Candidato).where(
                        Candidato.lote_id == lote_id,
                        Candidato.status == StatusCandidato.ERRO.value,
                    )
                )
            )
        )

    avaliacoes: list[Avaliacao] = []
    if vaga_id is not None:
        avaliacoes = await _recalibrar_vaga(vaga_id, regua, cliente, lote_id_custo=lote_id)

    await _marcar_lote_concluido(lote_id, vaga_titulo, avaliacoes, n_erros)


async def _recalibrar_vaga(
    vaga_id: int,
    regua: Regua,
    cliente: ClienteLLM,
    *,
    lote_id_custo: int | None = None,
    desempate_ia: bool = False,
) -> list[Avaliacao]:
    """Calibra + zonea TODOS os CVs prontos de uma vaga (pool acumulado).

    Carrega o pool da vaga (CVs `aguardando_lote` recém-prontos + `concluido` de
    lotes anteriores), recomputa percentil/zonas sobre o conjunto e persiste tudo
    como `concluido`.

    Por padrão **não** roda o desempate pareado por IA: ele faria N chamadas LLM
    sequenciais sobre o topo do pool a CADA lote, ficando lento e insustentável
    quando a vaga acumula centenas de CVs (era a causa do "travamento"). A ordem
    de empate já é resolvida deterministicamente por `chave_ordenacao`
    (críticos → resultados → experiência → menos flags → confiança).
    """
    with SessionLocal() as sessao:
        candidatos = list(
            sessao.scalars(
                select(Candidato)
                .join(Lote, Candidato.lote_id == Lote.id)
                .where(
                    Lote.vaga_id == vaga_id,
                    Candidato.status.in_(
                        [
                            StatusCandidato.AGUARDANDO_LOTE.value,
                            StatusCandidato.CONCLUIDO.value,
                        ]
                    ),
                )
            )
        )
        dados: list[tuple[int, str, Avaliacao]] = []
        textos: dict[str, str] = {}
        for c in candidatos:
            orm = c.avaliacao
            if orm is None:
                continue
            av = Avaliacao.model_validate(orm.avaliacao_json)
            dados.append((c.id, c.id_anonimo, av))
            textos[c.id_anonimo] = c.texto_cegado or ""

    if not dados:
        return []

    # Stage 6 — calibração sobre o pool inteiro da vaga.
    scores = {id_anon: av.score_final for _, id_anon, av in dados}
    calib = calibrar_lote(scores, regua.thresholds)
    for _, id_anon, av in dados:
        av.calibracao_lote = calib[id_anon]

    # Stage 8 — zonas por nota absoluta (+ ressalvas transparentes).
    for _, _id, av in dados:
        zona, recomendacao, rejeicao, motivo, ressalvas = classificar_zona(av, regua.thresholds)
        av.zona_decisao = zona
        av.recomendacao = recomendacao
        av.rejeicao_automatica_permitida = rejeicao
        av.motivo_zona = motivo
        av.ressalvas = ressalvas

    # Stage 7 — desempate pareado, só entre empates técnicos do topo (custa IA).
    if desempate_ia and lote_id_custo is not None:
        await _desempatar_topo(cliente, regua, dados, textos, lote_id_custo)

    # Stage 9 — síntese textual por IA (aderência + recomendação ao RH). Só para
    # quem ainda não tem (gate em campo vazio), para não repagar a cada novo lote;
    # falha/IA indisponível → fica vazio e a ficha cai no texto de template.
    await _gerar_sinteses(cliente, dados, lote_id_custo)

    # Persiste avaliações completas + zona no candidato (pool inteiro).
    with SessionLocal() as sessao:
        for cid, _id, av in dados:
            candidato = sessao.get(Candidato, cid)
            if candidato is None:
                continue
            candidato.zona = av.zona_decisao.value if av.zona_decisao else None
            candidato.status = StatusCandidato.CONCLUIDO.value
            candidato.estagio_atual = EstagioCandidato.CONCLUIDO.value
            _salvar_avaliacao(sessao, cid, av)
        sessao.commit()

    return [av for _, _, av in dados]


async def _desempatar_topo(
    cliente: ClienteLLM,
    regua: Regua,
    dados: list[tuple[int, str, Avaliacao]],
    textos: dict[str, str],
    lote_id: int,
) -> None:
    """Passada única de desempate entre pares empatados no topo do lote."""
    if not cliente.disponivel:
        return
    ordenados = sorted(dados, key=lambda it: chave_ordenacao(it[2]))[:_TOPO_DESEMPATE]
    i = 0
    while i < len(ordenados) - 1:
        _, id_a, av_a = ordenados[i]
        _, id_b, av_b = ordenados[i + 1]
        if abs(av_a.score_final - av_b.score_final) <= 5:
            try:
                vencedor = await estagios.desempatar_pareado(
                    cliente,
                    cv_a=textos.get(id_a, ""),
                    cv_b=textos.get(id_b, ""),
                    regua=regua,
                    semente=hash((id_a, id_b)) & 0xFFFF,
                    lote_id=lote_id,
                )
                if av_a.calibracao_lote:
                    av_a.calibracao_lote.comparacao_direta = True
                if av_b.calibracao_lote:
                    av_b.calibracao_lote.comparacao_direta = True
                # O resultado dá um leve nudge ao score (não muda a nota 0-4):
                # garante a ordenação relativa no empate.
                if vencedor == "b" and av_a.score_final == av_b.score_final:
                    av_b.score_final = round(av_b.score_final + 0.01, 2)
                elif vencedor == "a" and av_a.score_final == av_b.score_final:
                    av_a.score_final = round(av_a.score_final + 0.01, 2)
            except Exception:  # desempate é refinamento; falha → ordem determinística
                logger.exception("Falha no desempate %s vs %s (ignorado).", id_a, id_b)
        i += 1


async def _gerar_sinteses(
    cliente: ClienteLLM,
    dados: list[tuple[int, str, Avaliacao]],
    lote_id: int | None,
) -> None:
    """Gera os textos enriquecidos (aderência + recomendação) para quem não tem.

    Roda só sobre avaliações sem síntese (campo vazio) → não repaga CVs já
    sintetizados quando um novo lote recalibra o pool. Limita a concorrência e
    nunca derruba o lote: erro/IA indisponível deixa os campos vazios (a ficha usa
    o texto de template como fallback).
    """
    if not cliente.disponivel:
        return
    pendentes = [av for _, _, av in dados if not av.sintese_recomendacao]
    if not pendentes:
        return
    semaforo = asyncio.Semaphore(cfg_rt.obter_concorrencia())

    async def _uma(av: Avaliacao) -> None:
        async with semaforo:
            try:
                saida = await estagios.gerar_sintese(
                    cliente, avaliacao=av, lote_id=lote_id
                )
                # Truncação defensiva: limita o tamanho sem falhar validação.
                av.sintese_aderencia = saida.aderencia.strip()[:600]
                av.sintese_recomendacao = saida.recomendacao.strip()[:600]
            except Exception:  # síntese é enriquecimento; falha → fallback template
                logger.exception("Falha na síntese de %s (ignorado).", av.candidato)

    await asyncio.gather(*(_uma(av) for av in pendentes))


async def gerar_sinteses_vaga(vaga_id: int, cliente: ClienteLLM) -> int:
    """Gera as sínteses que faltam para os candidatos já avaliados de uma vaga.

    Usado após o reprocesso determinístico (que não chama IA): assim editar a
    régua preenche as sínteses pendentes (ex.: as que falharam antes), sem
    repagar as que já existem. Retorna quantas foram geradas.
    """
    if not cliente.disponivel:
        return 0
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
            if av.sintese_recomendacao:
                continue  # já tem síntese
            dados.append((c.id, c.id_anonimo, av))

    if not dados:
        return 0

    await _gerar_sinteses(cliente, dados, None)

    with SessionLocal() as sessao:
        for cid, _id, av in dados:
            if av.sintese_recomendacao:
                _salvar_avaliacao(sessao, cid, av)
        sessao.commit()
    return sum(1 for _, _, av in dados if av.sintese_recomendacao)


async def _marcar_lote_concluido(
    lote_id: int, vaga_titulo: str, avaliacoes: list[Avaliacao], n_erros: int
) -> None:
    """Atualiza contagens + taxa de auto-decisão (nível VAGA) e cria a notificação.

    `avaliacoes` é o pool inteiro da vaga; as contagens/taxa do lote refletem o
    acumulado. O progresso `concluidos/total` permanece deste lote (barra X/N).
    """
    zonas = [av.zona_decisao for av in avaliacoes if av.zona_decisao]
    n_entra = sum(1 for z in zonas if z == ZonaDecisao.ENTRA)
    n_avaliar = sum(1 for z in zonas if z == ZonaDecisao.AVALIAR)
    n_cai = sum(1 for z in zonas if z == ZonaDecisao.CAI)
    taxa = calcular_taxa_auto_decisao(zonas)

    with SessionLocal() as sessao:
        lote = sessao.get(Lote, lote_id)
        if lote is None:
            return
        # Progresso X/N deste lote: CVs concluídos OU com erro deste lote.
        concluidos_lote = (
            sessao.scalar(
                select(func.count(Candidato.id)).where(
                    Candidato.lote_id == lote_id,
                    Candidato.status.in_(
                        [StatusCandidato.CONCLUIDO.value, StatusCandidato.ERRO.value]
                    ),
                )
            )
            or 0
        )
        lote.status = StatusLote.CONCLUIDO.value
        lote.concluidos = concluidos_lote
        lote.n_entra = n_entra
        lote.n_avaliar = n_avaliar
        lote.n_cai = n_cai
        lote.taxa_auto_decisao = taxa
        lote.concluido_em = _dt.datetime.now()
        sessao.add(
            Notificacao(
                lote_id=lote_id,
                payload_json={
                    "titulo": "Triagem concluída",
                    "mensagem": (
                        f"Vaga {vaga_titulo}: {len(avaliacoes)} currículo(s) avaliado(s) no total"
                        + (f" ({n_erros} com erro neste lote)" if n_erros else "")
                    ),
                    "link": f"/triagem/lotes/{lote_id}",
                    "taxa_auto_decisao": taxa,
                },
            )
        )
        sessao.commit()
    logger.info(
        "Lote %s concluído (pool vaga: entra=%s avaliar=%s cai=%s taxa=%.2f)",
        lote_id, n_entra, n_avaliar, n_cai, taxa,
    )


def _salvar_avaliacao(sessao, candidato_id: int, avaliacao: Avaliacao) -> None:
    """Insere ou atualiza a Avaliacao ORM (upsert por candidato)."""
    orm = sessao.scalar(
        select(AvaliacaoORM).where(AvaliacaoORM.candidato_id == candidato_id)
    )
    payload = avaliacao.model_dump(mode="json")
    if orm is None:
        sessao.add(
            AvaliacaoORM(
                candidato_id=candidato_id,
                avaliacao_json=payload,
                score_final=avaliacao.score_final,
                zona=avaliacao.zona_decisao.value if avaliacao.zona_decisao else None,
            )
        )
    else:
        orm.avaliacao_json = payload
        orm.score_final = avaliacao.score_final
        orm.zona = avaliacao.zona_decisao.value if avaliacao.zona_decisao else None
