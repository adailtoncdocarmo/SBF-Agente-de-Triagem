"""Testes do roteador multi-provedor (ClienteLLM): fallback, timeout, telemetria."""

from __future__ import annotations

import asyncio

import pytest

from app import configuracao_runtime as cfg
from app.schemas.llm_flags import SaidaFlagsLLM
from app.triagem import cliente_llm
from app.triagem.cliente_llm import ClienteLLM, _Entrada
from app.triagem.provedores.base import Provedor, ResultadoExtracao


class ErroTransitorio(Exception):
    """Simula um 429/overload (rate limit) que some no retry."""

    status_code = 429


class ProvMock(Provedor):
    """Provedor de teste: 'ok' devolve, 'erro' levanta, 'lento' dorme."""

    def __init__(self, nome: str, comportamento: str) -> None:
        self.nome = nome
        self._c = comportamento

    @property
    def disponivel(self) -> bool:
        return True

    async def extrair(self, **_kw) -> ResultadoExtracao:
        if self._c == "erro":
            raise RuntimeError("provedor indisponível")
        if self._c == "lento":
            await asyncio.sleep(0.5)
        return ResultadoExtracao(dados=SaidaFlagsLLM(), tokens_in=10, tokens_out=5)


class ProvInstavel(Provedor):
    """Falha de forma transitória `n_falhas` vezes e depois responde."""

    nome = "anthropic"

    def __init__(self, n_falhas: int) -> None:
        self._restantes = n_falhas
        self.chamadas = 0

    @property
    def disponivel(self) -> bool:
        return True

    async def extrair(self, **_kw) -> ResultadoExtracao:
        self.chamadas += 1
        if self._restantes > 0:
            self._restantes -= 1
            raise ErroTransitorio("overloaded")
        return ResultadoExtracao(dados=SaidaFlagsLLM(), tokens_in=10, tokens_out=5)


def _entrada(nome: str, comportamento: str) -> _Entrada:
    modelo = "claude-sonnet-4-6" if nome == "anthropic" else "gpt-4o-mini"
    return _Entrada(ProvMock(nome, comportamento), modelo, 1.0, 1.0)


def _cliente_com(entradas: list[_Entrada], registros: list | None = None) -> ClienteLLM:
    cli = ClienteLLM(ao_registrar_custo=(registros.append if registros is not None else None))
    cli._cadeia = entradas  # injeta a cadeia de teste
    return cli


async def _chamar(cli: ClienteLLM):
    return await cli.extrair(skill_text="s", conteudo="c", schema=SaidaFlagsLLM, estagio="flags")


def test_primario_ok_nao_usa_fallback() -> None:
    registros: list = []
    cli = _cliente_com([_entrada("anthropic", "ok"), _entrada("openai", "ok")], registros)
    resultado = asyncio.run(_chamar(cli))
    assert isinstance(resultado, SaidaFlagsLLM)
    assert registros[0]["provedor"] == "anthropic"


def test_fallback_quando_primario_falha() -> None:
    registros: list = []
    cli = _cliente_com([_entrada("anthropic", "erro"), _entrada("openai", "ok")], registros)
    resultado = asyncio.run(_chamar(cli))
    assert isinstance(resultado, SaidaFlagsLLM)
    assert registros[-1]["provedor"] == "openai"  # respondeu o secundário


def test_fallback_quando_primario_timeout(monkeypatch) -> None:
    monkeypatch.setattr(cfg, "obter_timeout_llm", lambda: 0.05)
    registros: list = []
    cli = _cliente_com([_entrada("anthropic", "lento"), _entrada("openai", "ok")], registros)
    resultado = asyncio.run(_chamar(cli))
    assert isinstance(resultado, SaidaFlagsLLM)
    assert registros[-1]["provedor"] == "openai"


def test_cadeia_esgotada_levanta() -> None:
    cli = _cliente_com([_entrada("anthropic", "erro"), _entrada("openai", "erro")])
    with pytest.raises(RuntimeError, match="provedores falharam"):
        asyncio.run(_chamar(cli))


def test_retenta_no_mesmo_provedor_em_erro_transitorio(monkeypatch) -> None:
    # Sem backoff real no teste; o provedor falha 2x (429) e responde na 3ª.
    monkeypatch.setattr(cliente_llm, "_BACKOFF_BASE", 0.0)
    prov = ProvInstavel(n_falhas=2)
    cli = _cliente_com([_Entrada(prov, "claude-sonnet-4-6", 1.0, 1.0)])
    resultado = asyncio.run(_chamar(cli))
    assert isinstance(resultado, SaidaFlagsLLM)
    assert prov.chamadas == 3  # 2 falhas + 1 sucesso (não derrubou o CV)


def test_retenta_e_desiste_apos_limite(monkeypatch) -> None:
    # Falha transitória persistente → esgota as tentativas e levanta (sem reserva).
    monkeypatch.setattr(cliente_llm, "_BACKOFF_BASE", 0.0)
    prov = ProvInstavel(n_falhas=99)
    cli = _cliente_com([_Entrada(prov, "claude-sonnet-4-6", 1.0, 1.0)])
    with pytest.raises(RuntimeError, match="provedores falharam"):
        asyncio.run(_chamar(cli))
    assert prov.chamadas == 3  # tentou 3x antes de desistir
