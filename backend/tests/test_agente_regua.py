"""Testes da normalização da régua (Python puro, sem IA) + volatilidade."""

from __future__ import annotations

from app.schemas import Volatilidade
from app.schemas.llm_regua import ReguaPropostaLLM
from app.triagem.agente_regua import NOTA_MINIMA_PADRAO, montar_regua
from app.triagem.tabela_volatilidade import volatilidade_de


def test_montar_regua_normaliza_pesos_para_100() -> None:
    proposta = ReguaPropostaLLM(
        criterios_criticos=["tecnicas", "experiencia"],
        pesos_sugeridos={"tecnicas": 30, "experiencia": 35, "resultados": 10, "complexidade": 8, "setor": 12, "formacao": 18, "progressao": 6},
        competencias_detectadas=["atendimento ao cliente", "sistema PDV", "e-commerce"],
    )
    regua = montar_regua(proposta)
    assert sum(c.peso for c in regua.criterios) == 100
    assert {c.id for c in regua.criterios if c.e_critico} == {"tecnicas", "experiencia"}


def test_montar_regua_aplica_nota_minima_padrao() -> None:
    proposta = ReguaPropostaLLM(
        criterios_criticos=["complexidade"],
        pesos_sugeridos={},  # vazio → usa fallback, ainda soma 100
    )
    regua = montar_regua(proposta)
    assert sum(c.peso for c in regua.criterios) == 100
    c4 = regua.criterio("complexidade")
    assert c4.e_critico is True
    assert c4.nota_minima == NOTA_MINIMA_PADRAO  # default (o RH ajusta na tela)


def test_montar_regua_sem_criticos_usa_c1_default() -> None:
    proposta = ReguaPropostaLLM(
        criterios_criticos=[],
        pesos_sugeridos={},
    )
    regua = montar_regua(proposta)
    assert regua.criterio("tecnicas").e_critico is True


def test_volatilidade_por_tabela() -> None:
    assert volatilidade_de("e-commerce e marketplace") == Volatilidade.ALTA
    assert volatilidade_de("sistema PDV e controle de estoque") == Volatilidade.MEDIA
    assert volatilidade_de("atendimento ao cliente") == Volatilidade.BAIXA
    assert volatilidade_de("competência desconhecida") == Volatilidade.MEDIA  # default
