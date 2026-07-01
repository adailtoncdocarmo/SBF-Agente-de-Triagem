"""Testes do modelo de zonas por NOTA ABSOLUTA + ressalvas transparentes (Stage 8).

Princípios cobertos:
- a zona vem da faixa de nota (corte_verde/corte_amarelo);
- o único override duro (vermelho) é knockout OBJETIVO "não atende";
- ressalvas só rebaixam VERDE→AMARELO (nunca promovem, nunca mexem amarelo/vermelho);
- requisito SUBJETIVO nunca elimina nem rebaixa (só vira selo);
- rigor é monotônico (subir o corte nunca aumenta o nº de verdes).
"""

from __future__ import annotations

from app.schemas import (
    Avaliacao,
    Confianca,
    CriterioAvaliado,
    EstadoKnockout,
    Flags,
    FlagRiscoLLM,
    KnockoutAvaliadoLLM,
    RecenciaCalculada,
    Severidade,
    StatusCritico,
    Thresholds,
    Volatilidade,
    ZonaDecisao,
)
from app.schemas.avaliacao import ClarezaLLM
from app.triagem.zonas import calcular_taxa_auto_decisao, classificar_zona

CV, CA = 60, 35  # cortes default (Thresholds())


def _criterio(status: StatusCritico) -> CriterioAvaliado:
    return CriterioAvaliado(
        criterio="resultados",
        rotulo="Resultados e impacto",
        critico=True,
        peso=10,
        nota_0_4=1,
        nota_minima=3,
        status_critico=status,
        confianca_criterio=Confianca.ALTA,
        recencia=RecenciaCalculada(volatilidade=Volatilidade.BAIXA),
        pontuacao=2.5,
    )


def _avaliacao(
    *,
    score: float,
    confianca: Confianca = Confianca.MEDIA,
    portao_1: list[KnockoutAvaliadoLLM] | None = None,
    flags: Flags | None = None,
    criterios: list[CriterioAvaliado] | None = None,
) -> Avaliacao:
    return Avaliacao(
        candidato="CAND-X",
        vaga="x",
        portao_1=portao_1 or [],
        criterios=criterios or [],
        score_final=score,
        flags=flags or Flags(clareza=ClarezaLLM()),
        confianca=confianca,
    )


def _zona(av: Avaliacao, th: Thresholds | None = None) -> ZonaDecisao:
    return classificar_zona(av, th or Thresholds())[0]


# --- Faixa por nota -------------------------------------------------------- #
def test_nota_acima_do_corte_verde_entra() -> None:
    zona, _rec, rej, _m, ressalvas = classificar_zona(_avaliacao(score=70), Thresholds())
    assert zona == ZonaDecisao.ENTRA and rej is True and ressalvas == []


def test_nota_intermediaria_avaliar() -> None:
    assert _zona(_avaliacao(score=45)) == ZonaDecisao.AVALIAR


def test_nota_abaixo_do_corte_amarelo_cai() -> None:
    zona, _rec, rej, _m, _r = classificar_zona(_avaliacao(score=20), Thresholds())
    assert zona == ZonaDecisao.CAI and rej is True


# --- Knockout objetivo x subjetivo ---------------------------------------- #
def test_knockout_objetivo_nao_atende_derruba_mesmo_com_nota_alta() -> None:
    av = _avaliacao(
        score=90,
        portao_1=[KnockoutAvaliadoLLM(requisito="CNH B", estado=EstadoKnockout.NAO_ATENDE, objetivo=True)],
    )
    zona, _rec, rej, _m, _r = classificar_zona(av, Thresholds())
    assert zona == ZonaDecisao.CAI and rej is True


def test_knockout_subjetivo_nao_elimina_e_mantem_verde() -> None:
    av = _avaliacao(
        score=70,
        portao_1=[KnockoutAvaliadoLLM(requisito="Construir soluções de IA", estado=EstadoKnockout.NAO_ATENDE, objetivo=False)],
    )
    zona, _rec, _rej, _m, ressalvas = classificar_zona(av, Thresholds())
    assert zona == ZonaDecisao.ENTRA  # subjetivo não derruba
    assert any("Construir" in s for s in ressalvas)  # mas aparece como selo


def test_knockout_esperado_no_cv_nao_evidenciado_rebaixa_mesmo_subjetivo() -> None:
    # Requisito eliminatório "Esperado no CV" (tipico_no_cv=True) e o CV não comprova:
    # rebaixa verde→amarelo INDEPENDENTE do flag `objetivo` (quem manda é o seletor
    # do RH). Era esse acoplamento ao `objetivo` o bug do Adailton.
    av = _avaliacao(
        score=70,
        portao_1=[KnockoutAvaliadoLLM(requisito="Fluência em APIs", estado=EstadoKnockout.NAO_EVIDENCIADO, objetivo=False, tipico_no_cv=True)],
    )
    zona, _rec, _rej, _m, ressalvas = classificar_zona(av, Thresholds())
    assert zona == ZonaDecisao.AVALIAR
    assert any("Confirmar requisito" in s for s in ressalvas)


def test_knockout_perguntar_depois_nao_evidenciado_mantem_verde() -> None:
    # Requisito eliminatório "Perguntar depois" (tipico_no_cv=False) ausente: não penaliza.
    av = _avaliacao(
        score=70,
        portao_1=[KnockoutAvaliadoLLM(requisito="Disponibilidade p/ viagens", estado=EstadoKnockout.NAO_EVIDENCIADO, objetivo=False, tipico_no_cv=False)],
    )
    zona, _rec, _rej, _m, ressalvas = classificar_zona(av, Thresholds())
    assert zona == ZonaDecisao.ENTRA
    assert any("entrevista" in s.lower() for s in ressalvas)


def test_knockout_objetivo_nao_evidenciado_rebaixa_verde() -> None:
    av = _avaliacao(
        score=70,
        portao_1=[KnockoutAvaliadoLLM(requisito="Certificação X", estado=EstadoKnockout.NAO_EVIDENCIADO, objetivo=True, tipico_no_cv=True)],
    )
    assert _zona(av) == ZonaDecisao.AVALIAR  # típico no CV e ausente → rebaixa


def test_knockout_objetivo_atipico_no_cv_nao_evidenciado_mantem_verde() -> None:
    # CNH raramente aparece no CV (tipico_no_cv=False): a ausência NÃO rebaixa,
    # vira só um lembrete "verificar na entrevista".
    av = _avaliacao(
        score=70,
        portao_1=[KnockoutAvaliadoLLM(requisito="CNH B", estado=EstadoKnockout.NAO_EVIDENCIADO, objetivo=True, tipico_no_cv=False)],
    )
    zona, _rec, _rej, _m, ressalvas = classificar_zona(av, Thresholds())
    assert zona == ZonaDecisao.ENTRA  # ausência não penaliza
    assert any("entrevista" in s.lower() for s in ressalvas)


# --- Ressalvas rebaixam só VERDE, com motivo ------------------------------ #
def test_confianca_baixa_rebaixa_verde() -> None:
    assert _zona(_avaliacao(score=70, confianca=Confianca.BAIXA)) == ZonaDecisao.AVALIAR


def test_confianca_baixa_nao_resgata_vermelho() -> None:
    assert _zona(_avaliacao(score=20, confianca=Confianca.BAIXA)) == ZonaDecisao.CAI


def test_flag_media_nao_rebaixa() -> None:
    flags = Flags(risco=[FlagRiscoLLM(descricao="Datas sobrepostas", severidade=Severidade.MEDIA, acao="x")], clareza=ClarezaLLM())
    assert _zona(_avaliacao(score=70, flags=flags)) == ZonaDecisao.ENTRA


def test_flag_alta_rebaixa_verde() -> None:
    flags = Flags(risco=[FlagRiscoLLM(descricao="Inconsistência grave", severidade=Severidade.ALTA, acao="x")], clareza=ClarezaLLM())
    assert _zona(_avaliacao(score=70, flags=flags)) == ZonaDecisao.AVALIAR


def test_decisivo_validacao_rebaixa_verde() -> None:
    av = _avaliacao(score=70, criterios=[_criterio(StatusCritico.VALIDACAO)])
    assert _zona(av) == ZonaDecisao.AVALIAR


def test_decisivo_reprovado_rebaixa_mas_nao_vira_vermelho() -> None:
    av = _avaliacao(score=70, criterios=[_criterio(StatusCritico.REPROVADO)])
    assert _zona(av) == ZonaDecisao.AVALIAR  # rebaixa, não força vermelho


def test_ressalva_nao_promove_amarelo_nem_mexe_vermelho() -> None:
    # Um amarelo com ressalva continua amarelo; um vermelho continua vermelho.
    amarelo = _avaliacao(score=45, confianca=Confianca.BAIXA)
    assert _zona(amarelo) == ZonaDecisao.AVALIAR
    vermelho = _avaliacao(score=20, flags=Flags(risco=[FlagRiscoLLM(descricao="x", severidade=Severidade.ALTA, acao="x")], clareza=ClarezaLLM()))
    assert _zona(vermelho) == ZonaDecisao.CAI


# --- Rigor monotônico ------------------------------------------------------ #
def test_rigor_monotonico_subir_corte_nunca_aumenta_verde() -> None:
    scores = [70, 62, 50, 40, 30]
    flex = Thresholds(corte_verde=45, corte_amarelo=25)
    rig = Thresholds(corte_verde=75, corte_amarelo=50)
    n_flex = sum(1 for s in scores if _zona(_avaliacao(score=s), flex) == ZonaDecisao.ENTRA)
    n_rig = sum(1 for s in scores if _zona(_avaliacao(score=s), rig) == ZonaDecisao.ENTRA)
    assert n_flex >= n_rig and n_flex > 0


def test_taxa_auto_decisao() -> None:
    zonas = [ZonaDecisao.ENTRA, ZonaDecisao.CAI, ZonaDecisao.AVALIAR, ZonaDecisao.AVALIAR]
    assert calcular_taxa_auto_decisao(zonas) == 0.5
    assert calcular_taxa_auto_decisao([]) == 0.0
