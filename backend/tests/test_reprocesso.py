"""Testes do reprocesso da vaga: diff de régua, reconstrução de notas e o
recálculo determinístico (sem IA) sobre o pool acumulado.

Cobre os pedidos: (1) parâmetros não são congelados — salvar nova régua
reprocessa; (2) o acúmulo por vaga reranqueia todos os candidatos.
"""

from __future__ import annotations

import asyncio

from app.database import SessionLocal, criar_tabelas
from app.evaluation.dataset import carregar_vaga
from app.models_db import Candidato, Lote, Vaga
from app.schemas.avaliacao import Avaliacao
from app.schemas.enums import Confianca, EstadoKnockout, StatusCandidato, StatusLote
from app.schemas.llm_flags import ClarezaLLM, SaidaFlagsLLM
from app.schemas.llm_portao1 import KnockoutAvaliadoLLM, SaidaPortao1LLM
from app.schemas.llm_scoring import NotaCriterioLLM, SaidaScoringLLM
from app.schemas.regua import Knockout
from app.triagem import estagios, orquestrador
from app.triagem.portao2 import aplicar_portao2
from app.triagem.reprocesso import (
    _reconstruir_scoring,
    precisa_reextrair,
    reprocessar_vaga_deterministico,
)
from app.triagem.score import calcular_score

from tests.conftest import construir_notas, construir_regua

IDS = ["tecnicas", "experiencia", "resultados", "complexidade", "setor", "formacao", "progressao"]


# --------------------------------------------------------------------------- #
# Diff de régua (escolhe o caminho: determinístico × reextração com IA)
# --------------------------------------------------------------------------- #
def test_precisa_reextrair_so_pesos_e_falso() -> None:
    antiga = construir_regua()
    nova = antiga.model_copy(deep=True)
    # Reparticiona pesos mantendo soma 100 (muda só números).
    nova.criterios[0].peso += 5
    nova.criterios[1].peso -= 5
    assert precisa_reextrair(antiga, nova) is False


def test_precisa_reextrair_muda_rotulo_e_verdadeiro() -> None:
    antiga = construir_regua()
    nova = antiga.model_copy(deep=True)
    nova.criterios[0].rotulo = "Outro rótulo completamente diferente"
    assert precisa_reextrair(antiga, nova) is True


def test_precisa_reextrair_muda_knockout_e_verdadeiro() -> None:
    antiga = construir_regua()
    nova = antiga.model_copy(deep=True)
    nova.knockouts = [Knockout(requisito="CNH categoria D", justificativa_job_related="dirige")]
    assert precisa_reextrair(antiga, nova) is True


# --------------------------------------------------------------------------- #
# Reconstrução das notas brutas a partir da Avaliacao persistida
# --------------------------------------------------------------------------- #
def test_reconstruir_scoring_recupera_notas_brutas() -> None:
    regua = construir_regua()
    notas_brutas = {cid: 3 for cid in IDS}
    scoring = construir_notas(notas_brutas, confianca=Confianca.ALTA)
    status = aplicar_portao2(scoring, regua)
    _, criterios = calcular_score(scoring, regua, status, 2026)
    av = Avaliacao(candidato="CAND-0001", vaga="x", criterios=criterios)

    reconstruido = _reconstruir_scoring(av)
    for cid in IDS:
        assert reconstruido.por_id(cid).nota_0_4 == notas_brutas[cid]


# --------------------------------------------------------------------------- #
# Acúmulo por vaga + recálculo determinístico ponta a ponta
# --------------------------------------------------------------------------- #
async def _fake_portao1(cliente, *, texto_cegado, regua, **_kw) -> SaidaPortao1LLM:
    return SaidaPortao1LLM(
        knockouts=[KnockoutAvaliadoLLM(requisito="Disponibilidade", estado=EstadoKnockout.ATENDE)]
    )


async def _fake_flags(cliente, *, texto_cegado, **_kw) -> SaidaFlagsLLM:
    return SaidaFlagsLLM(risco=[], clareza=ClarezaLLM(confianca_avaliacao=Confianca.ALTA))


def _fake_scoring_por_nota(nota_forte: int, nota_fraco: int):
    async def _fn(cliente, *, texto_cegado, regua, **_kw) -> SaidaScoringLLM:
        base = nota_forte if "forte" in texto_cegado else nota_fraco
        # Notas NÃO-uniformes entre critérios — assim mover peso entre tecnicas e experiencia
        # altera de fato o score (sob notas uniformes o total não muda).
        def nota_de(cid: str) -> int:
            if cid == "experiencia":
                return max(0, base - 2)
            if cid == "tecnicas":
                return base
            return max(0, base - 1)

        return SaidaScoringLLM(
            notas=[
                NotaCriterioLLM(
                    criterio=cid,
                    nota_0_4=nota_de(cid),
                    evidencias=["evidência objetiva citada"],
                    confianca_criterio=Confianca.ALTA,
                )
                for cid in IDS
            ]
        )

    return _fn


def _criar_candidato(s, lote_id: int, nome: str, idx: int, texto: str) -> None:
    s.add(
        Candidato(
            lote_id=lote_id,
            nome_arquivo=nome,
            hash_cv=f"h-{nome}",
            id_anonimo=f"CAND-{idx:04d}",
            texto_cegado=texto,
            status=StatusCandidato.ENFILEIRADO.value,
        )
    )


def test_acumulo_por_vaga_e_reprocesso_deterministico(monkeypatch) -> None:
    monkeypatch.setattr(estagios, "avaliar_portao1", _fake_portao1)
    monkeypatch.setattr(estagios, "avaliar_criterios", _fake_scoring_por_nota(4, 2))
    monkeypatch.setattr(estagios, "avaliar_flags", _fake_flags)

    criar_tabelas()
    _, regua = carregar_vaga()

    with SessionLocal() as s:
        vaga = Vaga(
            titulo="Reprocesso", descricao="x",
            regua_json=regua.model_dump(mode="json"), congelada=True,
        )
        s.add(vaga)
        s.flush()
        lote_a = Lote(vaga_id=vaga.id, status=StatusLote.ENFILEIRADO.value, total=2)
        s.add(lote_a)
        s.flush()
        _criar_candidato(s, lote_a.id, "forte.txt", 1, "candidato forte")
        _criar_candidato(s, lote_a.id, "fraco.txt", 2, "candidato fraco")
        s.commit()
        vaga_id = vaga.id
        lote_a_id = lote_a.id

    asyncio.run(orquestrador.processar_lote(lote_a_id))

    # Segundo lote na MESMA vaga — deve somar ao pool e reranquear tudo.
    with SessionLocal() as s:
        lote_b = Lote(vaga_id=vaga_id, status=StatusLote.ENFILEIRADO.value, total=1)
        s.add(lote_b)
        s.flush()
        _criar_candidato(s, lote_b.id, "forte2.txt", 3, "outro candidato forte")
        s.commit()
        lote_b_id = lote_b.id

    asyncio.run(orquestrador.processar_lote(lote_b_id))

    # O pool da vaga tem os 3 candidatos concluídos (acúmulo entre lotes).
    with SessionLocal() as s:
        concluidos = list(
            s.query(Candidato)
            .join(Lote, Candidato.lote_id == Lote.id)
            .filter(Lote.vaga_id == vaga_id, Candidato.status == StatusCandidato.CONCLUIDO.value)
        )
        assert len(concluidos) == 3
        scores_antes = {c.id_anonimo: c.score_final for c in concluidos}

    # Reprocesso determinístico: zera o peso de tecnicas e joga em experiencia (sem IA).
    nova = regua.model_copy(deep=True)
    peso_c1 = nova.criterio("tecnicas").peso
    nova.criterios[0].peso = 0
    nova.criterios[1].peso += peso_c1

    afetados = reprocessar_vaga_deterministico(vaga_id, nova)
    assert afetados == 3

    with SessionLocal() as s:
        concluidos = list(
            s.query(Candidato)
            .join(Lote, Candidato.lote_id == Lote.id)
            .filter(Lote.vaga_id == vaga_id, Candidato.status == StatusCandidato.CONCLUIDO.value)
        )
        # Todos continuam concluídos e tiveram o score recalculado.
        assert len(concluidos) == 3
        for c in concluidos:
            assert c.status == StatusCandidato.CONCLUIDO.value
            assert c.avaliacao is not None
        scores_depois = {c.id_anonimo: c.score_final for c in concluidos}

    # Mudar a partição de pesos muda os scores (recálculo de fato aconteceu).
    assert scores_antes != scores_depois
