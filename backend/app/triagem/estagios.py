"""Estágios de julgamento (LLM) — Portão 1, scoring, flags, desempate.

Cada função monta o bloco de sistema **estável dentro do lote** (skill + contexto
da vaga) e passa só o CV como conteúdo volátil → cache hits a partir do 2º CV.
A IA só extrai sinais tipados; toda conta e decisão ficam no Python.
"""

from __future__ import annotations

import random

from app.schemas.avaliacao import Avaliacao
from app.schemas.enums import ZonaDecisao
from app.schemas.llm_comparacao import SaidaComparacaoLLM
from app.schemas.llm_flags import SaidaFlagsLLM
from app.schemas.llm_portao1 import SaidaPortao1LLM
from app.schemas.llm_scoring import SaidaScoringLLM
from app.schemas.llm_sintese import SaidaSinteseLLM
from app.schemas.regua import Regua
from app.triagem import contratos_skill
from app.triagem.cliente_llm import ClienteLLM

_ROTULO_ZONA = {
    ZonaDecisao.ENTRA: "Promissor (acima do corte)",
    ZonaDecisao.AVALIAR: "Revisar (faixa humana)",
    ZonaDecisao.CAI: "Fora do perfil (abaixo do corte)",
}


def _resumo_regua(regua: Regua) -> str:
    """Resumo legível da vaga para os prompts de scoring/comparação (cacheável)."""
    linhas = [
        "## Contexto da vaga",
        "Critérios e pesos:",
    ]
    for c in regua.criterios:
        marca = " (CRÍTICO)" if c.e_critico else ""
        linhas.append(f"- {c.id} {c.rotulo}: peso {c.peso}{marca}")
    if regua.knockouts:
        linhas.append("Requisitos eliminatórios: " + "; ".join(k.requisito for k in regua.knockouts))
    return "\n".join(linhas)


async def avaliar_portao1(
    cliente: ClienteLLM,
    *,
    texto_cegado: str,
    regua: Regua,
    lote_id: int | None = None,
    candidato_id: int | None = None,
) -> SaidaPortao1LLM:
    """Estágio 1 — knockout em 3 estados (LLM Haiku)."""
    if not regua.knockouts:
        return SaidaPortao1LLM(knockouts=[])
    sistema = contratos_skill.sistema("skill_portao1")
    requisitos = "\n".join(
        f"- {k.requisito} ({k.justificativa_job_related})" for k in regua.knockouts
    )
    conteudo = f"Requisitos eliminatórios:\n{requisitos}\n\nCurrículo:\n{texto_cegado}"
    return await cliente.extrair(
        skill_text=sistema,
        conteudo=conteudo,
        schema=SaidaPortao1LLM,
        estagio="portao1",
        max_tokens=3072,
        lote_id=lote_id,
        candidato_id=candidato_id,
    )


async def avaliar_criterios(
    cliente: ClienteLLM,
    *,
    texto_cegado: str,
    regua: Regua,
    lote_id: int | None = None,
    candidato_id: int | None = None,
) -> SaidaScoringLLM:
    """Estágio 2 — notas 0-4 dos 7 critérios (LLM Sonnet/Opus)."""
    sistema = contratos_skill.sistema("skill_scoring", _resumo_regua(regua))
    # Sem thinking estendido: a extração das notas 0-4 é estruturada e a nota
    # final é determinística (Python). Com thinking, a chamada ficava lenta e
    # estourava o timeout / truncava a saída — derrubando CVs. Sem ele, é rápida
    # e confiável, e 4096 tokens cobrem os 7 critérios com folga.
    return await cliente.extrair(
        skill_text=sistema,
        conteudo=f"Currículo:\n{texto_cegado}",
        schema=SaidaScoringLLM,
        estagio="scoring",
        max_tokens=4096,
        usar_thinking=False,
        lote_id=lote_id,
        candidato_id=candidato_id,
    )


async def avaliar_flags(
    cliente: ClienteLLM,
    *,
    texto_cegado: str,
    lote_id: int | None = None,
    candidato_id: int | None = None,
) -> SaidaFlagsLLM:
    """Estágio 3 — flags de risco + clareza → confiança (LLM Haiku)."""
    sistema = contratos_skill.sistema("skill_flags")
    return await cliente.extrair(
        skill_text=sistema,
        conteudo=f"Currículo:\n{texto_cegado}",
        schema=SaidaFlagsLLM,
        estagio="flags",
        max_tokens=3072,
        lote_id=lote_id,
        candidato_id=candidato_id,
    )


async def desempatar_pareado(
    cliente: ClienteLLM,
    *,
    cv_a: str,
    cv_b: str,
    regua: Regua,
    semente: int | None = None,
    lote_id: int | None = None,
) -> str:
    """Estágio 7 — desempate pareado. Retorna 'a', 'b' ou 'empate'.

    Randomiza a ordem A/B enviada ao LLM (anula o viés de posição) e remapeia o
    veredito para os candidatos originais. Só ordena empates — nunca muda nota.
    """
    rng = random.Random(semente)
    inverter = rng.random() < 0.5
    primeiro, segundo = (cv_b, cv_a) if inverter else (cv_a, cv_b)

    sistema = contratos_skill.sistema("skill_comparacao", _resumo_regua(regua))
    conteudo = f"Currículo A:\n{primeiro}\n\n---\n\nCurrículo B:\n{segundo}"
    veredito: SaidaComparacaoLLM = await cliente.extrair(
        skill_text=sistema,
        conteudo=conteudo,
        schema=SaidaComparacaoLLM,
        estagio="comparacao",
        max_tokens=1024,
        lote_id=lote_id,
    )
    if veredito.vencedor == "empate":
        return "empate"
    venceu_primeiro = veredito.vencedor == "A"
    # Remapeia: se invertemos, "A" enviado era o cv_b original.
    if inverter:
        return "b" if venceu_primeiro else "a"
    return "a" if venceu_primeiro else "b"


def _resumo_avaliacao(av: Avaliacao) -> str:
    """Resumo compacto da avaliação já pronta, para o prompt de síntese."""
    linhas: list[str] = [
        f"Nota final: {av.score_final:.0f}/100",
        f"Resultado: {_ROTULO_ZONA.get(av.zona_decisao, 'sem zona')}",
        "",
        "Critérios (nota 0-4 · peso · evidências/lacunas):",
    ]
    for c in av.criterios:
        marca = " [decisivo]" if c.critico else ""
        linha = f"- {c.rotulo}{marca}: nota {c.nota_0_4}, peso {c.peso}"
        if c.evidencias:
            linha += " · evidências: " + "; ".join(c.evidencias[:2])
        if c.lacunas:
            linha += " · lacunas: " + "; ".join(c.lacunas[:2])
        linhas.append(linha)
    if av.ressalvas:
        linhas.append("")
        linhas.append("A confirmar: " + "; ".join(av.ressalvas))
    if av.flags.risco:
        linhas.append("Riscos: " + "; ".join(f.descricao for f in av.flags.risco[:3]))
    return "\n".join(linhas)


async def gerar_sintese(
    cliente: ClienteLLM,
    *,
    avaliacao: Avaliacao,
    lote_id: int | None = None,
) -> SaidaSinteseLLM:
    """Estágio 9 — textos enriquecidos (aderência + recomendação) para a ficha.

    Recebe a avaliação JÁ calculada e só redige; não recalcula nota nem zona.
    """
    sistema = contratos_skill.sistema("skill_sintese")
    conteudo = (
        f"Vaga: {avaliacao.vaga}\n\nAvaliação do candidato:\n{_resumo_avaliacao(avaliacao)}"
    )
    return await cliente.extrair(
        skill_text=sistema,
        conteudo=conteudo,
        schema=SaidaSinteseLLM,
        estagio="sintese",
        max_tokens=1024,
        usar_thinking=False,
        lote_id=lote_id,
    )
