"""Roteador multi-provedor — extração estruturada com fallback e timeout.

Monta uma **cadeia** a partir dos dois slots provider-agnostic (Principal e
Secundária). Em timeout/indisponibilidade/erro, **cai para o próximo** — a fila
nunca trava esperando a API. Cada slot tem **um modelo**; o resultado é sempre o
mesmo schema Pydantic validado. Telemetria (RegistroCusto) registra o `provedor`
que de fato respondeu.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app import configuracao_runtime as cfg_rt
from app.config import configuracoes
from app.triagem.provedores import criar_provedor
from app.triagem.provedores.base import Provedor, RespostaInvalidaError, ResultadoExtracao

logger = logging.getLogger("triagem.cliente_llm")

T = TypeVar("T", bound=BaseModel)
RegistradorCusto = Callable[[dict[str, object]], None]

# Retry no MESMO provedor antes de cair para o próximo. Erros transitórios
# (rate limit 429, overload 529, 5xx) somem com uma espera curta — sem isso, um
# pico momentâneo da API derrubava CVs no meio de um lote grande.
_TENTATIVAS_POR_PROVEDOR = 3
_BACKOFF_BASE = 0.8  # segundos (cresce 0.8 → 1.6 → 3.2 + jitter)


def _deve_retentar(exc: Exception) -> bool:
    """True para erros intermitentes que valem retry no MESMO provedor.

    Cobre: saída inválida/truncada e erro de validação do schema (a geração é
    estocástica — quase sempre passa na 2ª) e instabilidade da API (rate limit
    429 / overload 529 / 5xx). NÃO inclui timeout (cai para o próximo provedor)
    nem credencial/bad-request (retry não ajuda).
    """
    if isinstance(exc, (RespostaInvalidaError, ValidationError)):
        return True
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        if status in (400, 401, 403, 404, 422):
            return False  # credencial / requisição inválida — retry não resolve
        if status == 429 or 500 <= status <= 599:
            return True
    nome = type(exc).__name__.lower()
    if any(
        k in nome
        for k in ("ratelimit", "overload", "internalservererror", "serviceunavailable", "apiconnection")
    ):
        return True
    msg = str(exc).lower()
    return any(
        k in msg
        for k in ("overloaded", "rate limit", "rate_limit", "429", "529", "too many requests", "temporarily")
    )


@dataclass
class _Entrada:
    """Uma entrada da cadeia: provedor + modelo + tarifas (para o custo)."""

    provedor: Provedor
    modelo: str
    rate_in: float
    rate_out: float


class ClienteLLM:
    """Cadeia de provedores: Principal → Secundária (reserva)."""

    def __init__(self, ao_registrar_custo: RegistradorCusto | None = None) -> None:
        self._cb = ao_registrar_custo
        self._cadeia = self._montar_cadeia()

    def _montar_cadeia(self) -> list[_Entrada]:
        cadeia: list[_Entrada] = []
        principal = cfg_rt.obter_principal()
        prov = criar_provedor(principal.provedor, principal.api_key, principal.modelo)
        if prov is not None and prov.disponivel:
            cadeia.append(_Entrada(prov, principal.modelo, principal.rate_in, principal.rate_out))

        secundaria = cfg_rt.obter_secundaria()
        if secundaria is not None:
            prov2 = criar_provedor(secundaria.provedor, secundaria.api_key, secundaria.modelo)
            if prov2 is not None and prov2.disponivel:
                cadeia.append(
                    _Entrada(prov2, secundaria.modelo, secundaria.rate_in, secundaria.rate_out)
                )
        return cadeia

    @property
    def disponivel(self) -> bool:
        return bool(self._cadeia)

    async def extrair(
        self,
        *,
        skill_text: str,
        conteudo: str,
        schema: type[T],
        estagio: str,
        max_tokens: int = 2048,
        instrucao_extra: str = "",
        usar_thinking: bool = True,
        timeout_override: float | None = None,
        lote_id: int | None = None,
        candidato_id: int | None = None,
    ) -> T:
        if not self._cadeia:
            raise RuntimeError(
                "Nenhum provedor de IA configurado — registre a chave em Configurações."
            )
        if instrucao_extra:
            skill_text = f"{skill_text}\n\n{instrucao_extra}"

        # `timeout_override` permite uma folga maior em chamadas interativas
        # one-shot (ex.: gerar a régua), sem afrouxar o timeout do pipeline.
        timeout = timeout_override or cfg_rt.obter_timeout_llm()
        ultimo_erro: Exception | None = None
        for entrada in self._cadeia:
            for tentativa in range(_TENTATIVAS_POR_PROVEDOR):
                try:
                    inicio = time.monotonic()
                    resultado = await asyncio.wait_for(
                        entrada.provedor.extrair(
                            skill_text=skill_text,
                            conteudo=conteudo,
                            schema=schema,
                            modelo=entrada.modelo,
                            max_tokens=max_tokens,
                            usar_thinking=usar_thinking,
                        ),
                        timeout=timeout,
                    )
                    latencia_ms = int((time.monotonic() - inicio) * 1000)
                    self._registrar(entrada, estagio, resultado, latencia_ms, lote_id, candidato_id)
                    return resultado.dados  # type: ignore[return-value]
                except Exception as exc:
                    ultimo_erro = exc
                    ultima = tentativa == _TENTATIVAS_POR_PROVEDOR - 1
                    if _deve_retentar(exc) and not ultima:
                        espera = round(_BACKOFF_BASE * (2**tentativa) + random.uniform(0, 0.4), 2)
                        logger.warning(
                            "Provedor '%s' instável (estágio=%s, %s) — retry %d/%d em %.1fs.",
                            entrada.provedor.nome, estagio, type(exc).__name__,
                            tentativa + 1, _TENTATIVAS_POR_PROVEDOR, espera,
                        )
                        await asyncio.sleep(espera)
                        continue
                    # Erro não-transitório ou tentativas esgotadas → próximo provedor.
                    logger.warning(
                        "Provedor '%s' falhou (estágio=%s, %s) — tentando o próximo.",
                        entrada.provedor.nome, estagio, type(exc).__name__,
                    )
                    break

        raise RuntimeError(f"Todos os provedores falharam no estágio '{estagio}'.") from ultimo_erro

    def _registrar(
        self,
        entrada: _Entrada,
        estagio: str,
        resultado: ResultadoExtracao,
        latencia_ms: int,
        lote_id: int | None,
        candidato_id: int | None,
    ) -> None:
        if self._cb is None:
            return
        if entrada.provedor.nome == "anthropic":
            custo = configuracoes.custo_usd(
                entrada.modelo, resultado.tokens_in, resultado.tokens_out, resultado.tokens_cache_read
            )
        else:
            custo = round(
                resultado.tokens_in / 1e6 * entrada.rate_in
                + resultado.tokens_out / 1e6 * entrada.rate_out,
                6,
            )
        self._cb(
            {
                "lote_id": lote_id,
                "candidato_id": candidato_id,
                "estagio": estagio,
                "provedor": entrada.provedor.nome,
                "modelo": entrada.modelo,
                "tokens_in": resultado.tokens_in,
                "tokens_out": resultado.tokens_out,
                "tokens_cache_read": resultado.tokens_cache_read,
                "custo_usd": custo,
                "latencia_ms": latencia_ms,
            }
        )
