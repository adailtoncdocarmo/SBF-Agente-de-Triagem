"""Teste de integração do orquestrador: roda `processar_lote` ponta a ponta com
os estágios LLM **mockados** (sem chave de API), contra o banco real.

Cobre o caminho que o teste unitário não pega: persistência ORM, fluxo async
per-CV → lote-level, calibração, zonas e contagens do lote.
"""

from __future__ import annotations

import asyncio

from app.database import SessionLocal, criar_tabelas
from app.models_db import Candidato, Lote, Notificacao, Vaga
from app.schemas.enums import StatusCandidato, StatusLote
from app.schemas.llm_flags import ClarezaLLM, SaidaFlagsLLM
from app.schemas.llm_portao1 import KnockoutAvaliadoLLM, SaidaPortao1LLM
from app.schemas.llm_scoring import NotaCriterioLLM, SaidaScoringLLM
from app.schemas.enums import Confianca, EstadoKnockout
from app.evaluation.dataset import carregar_vaga
from app.triagem import estagios, orquestrador


async def _fake_portao1(cliente, *, texto_cegado, regua, **_kw) -> SaidaPortao1LLM:
    return SaidaPortao1LLM(
        knockouts=[KnockoutAvaliadoLLM(requisito="Disponibilidade", estado=EstadoKnockout.ATENDE)]
    )


async def _fake_scoring(cliente, *, texto_cegado, regua, **_kw) -> SaidaScoringLLM:
    # Forte: notas altas → entra. Fraco: nota 1 COM evidência (abaixo do piso 2,
    # mas com evidência presente) → crítico reprovado → cai (auto-descarte).
    nota = 4 if "forte" in texto_cegado else 1
    return SaidaScoringLLM(
        notas=[
            NotaCriterioLLM(
                criterio=cid,
                nota_0_4=nota,
                evidencias=["evidência objetiva citada"],
                confianca_criterio=Confianca.ALTA,
            )
            for cid in ["tecnicas", "experiencia", "resultados", "complexidade", "setor", "formacao", "progressao"]
        ]
    )


async def _fake_flags(cliente, *, texto_cegado, **_kw) -> SaidaFlagsLLM:
    return SaidaFlagsLLM(risco=[], clareza=ClarezaLLM(confianca_avaliacao=Confianca.ALTA))


def test_processar_lote_ponta_a_ponta(monkeypatch) -> None:
    monkeypatch.setattr(estagios, "avaliar_portao1", _fake_portao1)
    monkeypatch.setattr(estagios, "avaliar_criterios", _fake_scoring)
    monkeypatch.setattr(estagios, "avaliar_flags", _fake_flags)

    criar_tabelas()
    _, regua = carregar_vaga()

    with SessionLocal() as s:
        vaga = Vaga(titulo="Teste Orq", descricao="x", regua_json=regua.model_dump(mode="json"), congelada=True)
        s.add(vaga)
        s.flush()
        lote = Lote(vaga_id=vaga.id, status=StatusLote.ENFILEIRADO.value, total=2)
        s.add(lote)
        s.flush()
        s.add(Candidato(lote_id=lote.id, nome_arquivo="forte.txt", hash_cv="h1", id_anonimo="CAND-0001", texto_cegado="candidato forte com vendas e PDV", status=StatusCandidato.ENFILEIRADO.value))
        s.add(Candidato(lote_id=lote.id, nome_arquivo="fraco.txt", hash_cv="h2", id_anonimo="CAND-0002", texto_cegado="sem experiencia relevante", status=StatusCandidato.ENFILEIRADO.value))
        s.commit()
        lote_id = lote.id

    asyncio.run(orquestrador.processar_lote(lote_id))

    with SessionLocal() as s:
        lote = s.get(Lote, lote_id)
        assert lote.status == StatusLote.CONCLUIDO.value
        assert lote.concluidos == 2
        assert lote.taxa_auto_decisao is not None
        candidatos = {c.id_anonimo: c for c in lote.candidatos}
        assert candidatos["CAND-0001"].status == StatusCandidato.CONCLUIDO.value
        assert candidatos["CAND-0001"].zona == "entra"  # forte → entra
        assert candidatos["CAND-0002"].zona == "cai"  # fraco → cai
        assert candidatos["CAND-0001"].avaliacao is not None
        # Notificação criada ao concluir.
        notifs = list(s.query(Notificacao).filter(Notificacao.lote_id == lote_id))
        assert len(notifs) == 1
