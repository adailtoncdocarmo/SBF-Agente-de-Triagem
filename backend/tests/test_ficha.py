"""Testes do estágio 9 (ranking + ficha) — exercita o caminho lote-level
completo (calibração → zonas → montar_ranking_vaga/ficha) que monta a saída final."""

from __future__ import annotations

from app.schemas import Confianca, StatusCritico, ZonaDecisao
from app.triagem.calibracao import calibrar_lote
from app.triagem.ficha import montar_ficha, montar_ranking_vaga
from app.triagem.portao2 import aplicar_portao2
from app.triagem.score import calcular_score
from app.triagem.zonas import classificar_zona
from app.schemas.avaliacao import Avaliacao, Flags
from app.schemas.llm_flags import ClarezaLLM
from tests.conftest import construir_notas, construir_regua


def _avaliar(id_anonimo: str, notas: dict[str, int], conf: Confianca) -> Avaliacao:
    regua = construir_regua(criticos=("tecnicas",), pisos={"tecnicas": 2})
    saida = construir_notas(notas, confianca=conf)
    status = aplicar_portao2(saida, regua)
    score, criterios = calcular_score(saida, regua, status, ano_atual=2026)
    return Avaliacao(
        candidato=id_anonimo,
        vaga="Vendedor de Loja",
        criterios=criterios,
        score_final=score,
        flags=Flags(clareza=ClarezaLLM(confianca_avaliacao=conf)),
        confianca=conf,
    )


def test_ranking_e_ficha_lote_completo() -> None:
    forte = _avaliar("CAND-0001", {c: 4 for c in ["tecnicas", "experiencia", "resultados", "complexidade", "setor", "formacao", "progressao"]}, Confianca.ALTA)
    fraco = _avaliar("CAND-0002", {c: 0 for c in ["tecnicas", "experiencia", "resultados", "complexidade", "setor", "formacao", "progressao"]}, Confianca.ALTA)
    avaliacoes = {"CAND-0001": forte, "CAND-0002": fraco}

    # Lote-level: calibração + zonas (o caminho que tinha o bug av.zona).
    calib = calibrar_lote({k: v.score_final for k, v in avaliacoes.items()}, construir_regua().thresholds)
    for k, av in avaliacoes.items():
        av.calibracao_lote = calib[k]
        zona, rec, _rej, motivo, ressalvas = classificar_zona(av, construir_regua().thresholds)
        av.zona_decisao, av.recomendacao, av.motivo_zona, av.ressalvas = zona, rec, motivo, ressalvas

    itens = [(1, "forte.txt", None, forte), (2, "fraco.txt", None, fraco)]
    ranking = montar_ranking_vaga(7, "Vendedor de Loja", itens)
    assert ranking.total_avaliados == 2
    assert 0.0 <= ranking.taxa_auto_decisao <= 1.0
    # O forte deve cair em "entra"; o fraco em "cai".
    assert forte.zona_decisao == ZonaDecisao.ENTRA
    assert fraco.zona_decisao == ZonaDecisao.CAI

    ficha = montar_ficha(1, "forte.txt", forte, posicao=1, total_lote=2)
    assert ficha.score_final == forte.score_final
    assert ficha.recomendacao is not None
    assert ficha.zona == ZonaDecisao.ENTRA
    assert "Aderência" in ficha.justificativa
