"""Testes das correções da rodada 2 (bugs reportados pelo usuário).

Cobrem o que foi cobrado: o endpoint do CV funciona de verdade, a nota mínima
persiste no round-trip e produz o resultado certo no Portão 2/zona, a síntese não
quebra com texto longo, e DOCX/PDF-imagem são tratados corretamente.
"""

from __future__ import annotations

import datetime as _dt
import io

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models_db import Avaliacao as AvaliacaoORM
from app.models_db import Candidato, Lote, Vaga
from app.schemas import (
    Avaliacao,
    Confianca,
    EstadoKnockout,
    Flags,
    StatusCritico,
    Thresholds,
    ZonaDecisao,
)
from app.schemas.regua import CriterioRegua, Regua
from app.schemas.llm_scoring import SaidaScoringLLM
from app.schemas.llm_sintese import SaidaSinteseLLM
from app.triagem.ingest import extrair_texto
from app.triagem.portao2 import aplicar_portao2
from app.triagem.score import calcular_score
from app.triagem.zonas import classificar_zona
from tests.conftest import construir_notas, construir_regua

_ANO = _dt.date.today().year


# --- A) Endpoint do CV (PDF) realmente funciona ---------------------------- #
def _criar_candidato_com_arquivo(arquivo: bytes | None, mime: str | None) -> int:
    """Cria Vaga→Lote→Candidato no banco de teste e devolve o candidato_id."""
    with SessionLocal() as s:
        vaga = Vaga(
            titulo="Vaga teste",
            descricao="desc",
            regua_json=construir_regua().model_dump(mode="json"),
            congelada=True,
        )
        s.add(vaga)
        s.flush()
        lote = Lote(vaga_id=vaga.id, status="concluido", total=1)
        s.add(lote)
        s.flush()
        cand = Candidato(
            lote_id=lote.id,
            nome_arquivo="cv-teste.pdf",
            hash_cv="hash-teste",
            id_anonimo="CAND-0001",
            texto_cegado="texto cegado",
            arquivo_original=arquivo,
            arquivo_mime=mime,
            status="concluido",
        )
        s.add(cand)
        s.commit()
        return cand.id


def test_endpoint_cv_devolve_arquivo_quando_existe() -> None:
    cid = _criar_candidato_com_arquivo(b"%PDF-1.4 conteudo", "application/pdf")
    with TestClient(app) as client:
        resp = client.get(f"/api/avaliacoes/{cid}/cv")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/pdf")
    assert resp.content == b"%PDF-1.4 conteudo"


def test_endpoint_cv_404_amigavel_quando_ausente() -> None:
    cid = _criar_candidato_com_arquivo(None, None)
    with TestClient(app) as client:
        resp = client.get(f"/api/avaliacoes/{cid}/cv")
    assert resp.status_code == 404
    assert "indispon" in resp.json()["detail"].lower()


# --- D) nota_minima persiste no round-trip (e aceita a chave antiga) -------- #
def test_nota_minima_round_trip_preserva_valor() -> None:
    regua = construir_regua(criticos=("tecnicas",), pisos={"tecnicas": 1})
    bruto = regua.model_dump(mode="json")
    assert bruto["criterios"][0]["nota_minima"] == 1  # serializa pelo nome certo
    revalidada = Regua.model_validate(bruto)
    assert revalidada.criterio("tecnicas").nota_minima == 1


def test_nota_minima_le_chave_legada_piso_senioridade() -> None:
    crit = CriterioRegua.model_validate(
        {"id": "tecnicas", "rotulo": "x", "peso": 100, "e_critico": True, "piso_senioridade": 3}
    )
    assert crit.nota_minima == 3  # alias retrocompatível


# --- D) cenário do usuário: nota 2 ≥ nota_minima 1 → APROVADO e verde ------- #
def test_decisivo_nota_acima_do_minimo_aprova_e_fica_verde() -> None:
    regua = construir_regua(
        criticos=("tecnicas",),
        pisos={"tecnicas": 1},
        thresholds=Thresholds(corte_verde=45, corte_amarelo=25),  # rigor Flexível
    )
    notas = construir_notas({c: 2 for c in [
        "tecnicas", "experiencia", "resultados", "complexidade", "setor", "formacao", "progressao",
    ]})
    status = aplicar_portao2(notas, regua)
    assert status["tecnicas"] == StatusCritico.APROVADO  # 2 ≥ 1

    score, criterios = calcular_score(notas, regua, status, _ANO)
    av = Avaliacao(
        candidato="CAND-0001",
        vaga="v",
        criterios=criterios,
        score_final=score,
        confianca=Confianca.ALTA,
        flags=Flags(),
    )
    zona, _rec, _rej, _m, _r = classificar_zona(av, regua.thresholds)
    assert zona == ZonaDecisao.ENTRA  # score 50 ≥ 45, sem ressalvas → verde


# --- B) Síntese não quebra com texto longo (sem max_length rígido) --------- #
def test_sintese_aceita_texto_longo() -> None:
    saida = SaidaSinteseLLM(aderencia="a" * 700, recomendacao="b" * 700)
    assert len(saida.aderencia) == 700 and len(saida.recomendacao) == 700


# --- E) DOCX é lido; arquivo sem texto retorna vazio ----------------------- #
def test_extrair_texto_docx() -> None:
    from docx import Document

    doc = Document()
    doc.add_paragraph("Experiência em varejo e atendimento ao cliente.")
    buffer = io.BytesIO()
    doc.save(buffer)
    texto = extrair_texto("curriculo.docx", buffer.getvalue())
    assert "varejo" in texto.lower()


def test_extrair_texto_pdf_sem_texto_retorna_vazio() -> None:
    # Bytes que não são um PDF válido → sem texto extraível (simula imagem/corrompido).
    texto = extrair_texto("scan.pdf", b"\x00\x01\x02 not a real pdf")
    assert texto.strip() == ""


# --- Bug do Adailton: marcar "Eliminatório" depois reflete no reprocesso ---- #
def test_aplicar_flags_knockout_casa_por_prefixo() -> None:
    """A IA devolve o requisito com a justificativa anexada; o casamento por
    prefixo precisa fixar objetivo/tipico_no_cv e limpar o texto."""
    from app.schemas.llm_portao1 import KnockoutAvaliadoLLM
    from app.schemas.regua import Knockout
    from app.triagem.zonas import aplicar_flags_knockout

    regua = construir_regua()
    regua = regua.model_copy(
        update={"knockouts": [Knockout(requisito="Python e APIs", objetivo=True, tipico_no_cv=True)]}
    )
    portao = [
        KnockoutAvaliadoLLM(
            requisito="Python e APIs (domínio técnico verificável no CV)",
            estado=EstadoKnockout.NAO_EVIDENCIADO,
            objetivo=False,
            tipico_no_cv=True,
        )
    ]
    aplicar_flags_knockout(portao, regua)
    assert portao[0].objetivo is True  # veio da régua
    assert portao[0].requisito == "Python e APIs"  # texto limpo (sem justificativa)


def test_reprocesso_aplica_eliminatorio_e_rebaixa_candidato() -> None:
    """Cenário do usuário: marcar um requisito existente como Eliminatório +
    Esperado no CV depois da avaliação deve rebaixar quem não evidencia (verde→amarelo)."""
    from app.schemas.enums import ZonaDecisao as Z
    from app.schemas.llm_portao1 import KnockoutAvaliadoLLM
    from app.schemas.regua import Knockout
    from app.triagem.reprocesso import reprocessar_vaga_deterministico

    regua = construir_regua(criticos=("tecnicas",))
    # Cenário REAL da vaga 10: a régua guarda o knockout com objetivo=False
    # (a IA não o marcou como objetivo) — mesmo assim "Esperado no CV"
    # (tipico_no_cv=True) deve rebaixar quem não evidencia.
    regua = regua.model_copy(
        update={"knockouts": [Knockout(requisito="Python e APIs", objetivo=False, tipico_no_cv=True)]}
    )
    notas = construir_notas({c: 3 for c in [
        "tecnicas", "experiencia", "resultados", "complexidade", "setor", "formacao", "progressao",
    ]})
    status = aplicar_portao2(notas, regua)
    score, criterios = calcular_score(notas, regua, status, _ANO)
    av = Avaliacao(
        candidato="CAND-0001",
        vaga="v",
        criterios=criterios,
        score_final=score,  # 75 → verde
        confianca=Confianca.ALTA,
        # Estado como a IA salvou: requisito com justificativa anexada, objetivo desatualizado.
        portao_1=[
            KnockoutAvaliadoLLM(
                requisito="Python e APIs (verificável no CV)",
                estado=EstadoKnockout.NAO_EVIDENCIADO,
                objetivo=False,
                tipico_no_cv=True,
            )
        ],
        zona_decisao=Z.ENTRA,
    )

    with SessionLocal() as s:
        vaga = Vaga(titulo="v", descricao="d", regua_json=regua.model_dump(mode="json"), congelada=True)
        s.add(vaga)
        s.flush()
        lote = Lote(vaga_id=vaga.id, status="concluido", total=1)
        s.add(lote)
        s.flush()
        cand = Candidato(
            lote_id=lote.id, nome_arquivo="a.pdf", hash_cv="h1", id_anonimo="CAND-0001",
            status="concluido", score_final=score, zona="entra",
        )
        s.add(cand)
        s.flush()
        s.add(AvaliacaoORM(candidato_id=cand.id, avaliacao_json=av.model_dump(mode="json"), score_final=score, zona="entra"))
        s.commit()
        vaga_id, cand_id = vaga.id, cand.id

    reprocessar_vaga_deterministico(vaga_id, regua)

    with SessionLocal() as s:
        orm = s.get(Candidato, cand_id).avaliacao
        depois = Avaliacao.model_validate(orm.avaliacao_json)
    assert depois.zona_decisao == Z.AVALIAR  # rebaixado: eliminatório esperado no CV, não evidenciado
    assert depois.portao_1[0].objetivo is False  # rebaixe NÃO depende de objetivo
    assert depois.portao_1[0].tipico_no_cv is True  # quem manda é o seletor do RH
    assert depois.portao_1[0].requisito == "Python e APIs"  # texto limpo
