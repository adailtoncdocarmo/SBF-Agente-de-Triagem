"""Testes da pinagem de contrato — o contrato é sempre injetado por código.

Mesmo que o RH apague todo o texto editável da skill, o contrato de formato
(constante Python) precisa continuar presente no `skill_text` enviado à IA.
Sem chamar API real: um provedor de teste captura o `skill_text` recebido.
"""

from __future__ import annotations

import asyncio

import pytest

from app.evaluation.dataset import carregar_vaga
from app.schemas.avaliacao import Avaliacao
from app.schemas.llm_comparacao import SaidaComparacaoLLM
from app.schemas.llm_regua import ReguaPropostaLLM
from app.triagem import agente_regua, contratos_skill, estagios
from app.triagem.cliente_llm import ClienteLLM, _Entrada
from app.triagem.provedores.base import Provedor, ResultadoExtracao

_SKILLS = [
    "skill_regua",
    "skill_portao1",
    "skill_scoring",
    "skill_flags",
    "skill_comparacao",
    "skill_sintese",
]


def _amostra_valida(schema):
    """Instância mínima válida do schema (alguns têm campos obrigatórios)."""
    if schema is ReguaPropostaLLM:
        return ReguaPropostaLLM()
    if schema is SaidaComparacaoLLM:
        return SaidaComparacaoLLM(vencedor="empate")
    return schema()  # portao1/scoring/flags/sintese têm tudo com default


class ProvCaptura(Provedor):
    """Provedor de teste que registra o `skill_text` recebido."""

    nome = "anthropic"

    def __init__(self) -> None:
        self.skill_text_recebido = ""

    @property
    def disponivel(self) -> bool:
        return True

    async def extrair(self, *, skill_text, schema, **_kw) -> ResultadoExtracao:
        self.skill_text_recebido = skill_text
        return ResultadoExtracao(dados=_amostra_valida(schema), tokens_in=1, tokens_out=1)


def _cliente(prov: ProvCaptura) -> ClienteLLM:
    cli = ClienteLLM(ao_registrar_custo=None)
    cli._cadeia = [_Entrada(prov, "claude-haiku-4-5", 1.0, 1.0)]
    return cli


def _rodar(nome: str, prov: ProvCaptura) -> None:
    """Dispara o estágio correspondente à skill, com o provedor de captura."""
    cli = _cliente(prov)
    _, regua = carregar_vaga()
    if nome == "skill_regua":
        asyncio.run(agente_regua.propor_regua(cli, "Vaga de teste para varejo operacional."))
    elif nome == "skill_portao1":
        asyncio.run(estagios.avaliar_portao1(cli, texto_cegado="cv de teste", regua=regua))
    elif nome == "skill_scoring":
        asyncio.run(estagios.avaliar_criterios(cli, texto_cegado="cv de teste", regua=regua))
    elif nome == "skill_flags":
        asyncio.run(estagios.avaliar_flags(cli, texto_cegado="cv de teste"))
    elif nome == "skill_comparacao":
        asyncio.run(estagios.desempatar_pareado(cli, cv_a="cv 1", cv_b="cv 2", regua=regua))
    elif nome == "skill_sintese":
        asyncio.run(
            estagios.gerar_sintese(cli, avaliacao=Avaliacao(candidato="CAND-0001", vaga="Vaga"))
        )


@pytest.mark.parametrize("nome", _SKILLS)
def test_contrato_e_prefixo_do_sistema(nome: str) -> None:
    prov = ProvCaptura()
    _rodar(nome, prov)
    assert prov.skill_text_recebido.startswith(contratos_skill.contrato(nome))


@pytest.mark.parametrize("nome", _SKILLS)
def test_contrato_persiste_mesmo_com_skill_vazia(nome: str, monkeypatch) -> None:
    # Simula uma skill com texto vazio: o contrato pinado precisa continuar presente.
    monkeypatch.setattr("app.triagem.contratos_skill.carregar_skill", lambda _n: "")
    prov = ProvCaptura()
    _rodar(nome, prov)
    contrato = contratos_skill.contrato(nome)
    assert contrato and contrato in prov.skill_text_recebido
    assert prov.skill_text_recebido.startswith(contrato)


def test_contrato_skill_desconhecida_vazio() -> None:
    assert contratos_skill.contrato("nao_existe") == ""
