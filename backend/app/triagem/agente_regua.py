"""Agente Régua — descrição da vaga → régua estruturada (1×/vaga).

A IA propõe (`ReguaPropostaLLM`); o Python **normaliza os pesos para somar 100**,
casa as competências com a tabela estática de volatilidade e aplica a nota mínima
padrão dos críticos — produzindo uma `Regua` válida e congelável. `montar_regua`
é puro e testável; `propor_regua` é a etapa com IA.
"""

from __future__ import annotations

from app import configuracao_runtime as cfg_rt
from app.triagem import contratos_skill
from app.schemas.llm_regua import ReguaPropostaLLM
from app.schemas.regua import (
    CriterioRegua,
    Regua,
    Thresholds,
    VolatilidadeCompetencia,
)
from app.schemas.enums import ROTULOS_CRITERIOS
from app.triagem.cliente_llm import ClienteLLM
from app.triagem.tabela_volatilidade import volatilidade_de

IDS = list(ROTULOS_CRITERIOS)

# Nota mínima padrão dos critérios decisivos (o RH ajusta por critério na tela).
NOTA_MINIMA_PADRAO = 2

# Distribuição base (operacional) usada como fallback se o LLM não sugerir pesos.
_PESOS_FALLBACK = {
    "tecnicas": 25,
    "experiencia": 30,
    "resultados": 8,
    "complexidade": 7,
    "setor": 10,
    "formacao": 15,
    "progressao": 5,
}


def _renormalizar_pesos(brutos: dict[str, int]) -> dict[str, int]:
    """Renormaliza os pesos para somar exatamente 100 (maior resto, inteiros)."""
    valores = {cid: max(0, int(brutos.get(cid, 0))) for cid in IDS}
    total = sum(valores.values())
    if total == 0:
        return dict(_PESOS_FALLBACK)
    exatos = {cid: valores[cid] / total * 100 for cid in IDS}
    inteiros = {cid: int(exatos[cid]) for cid in IDS}
    resto = 100 - sum(inteiros.values())
    # Distribui o resto pelos maiores resíduos fracionários.
    por_fracao = sorted(IDS, key=lambda c: exatos[c] - inteiros[c], reverse=True)
    for i in range(resto):
        inteiros[por_fracao[i % len(IDS)]] += 1
    return inteiros


def _selecionar_criticos(criterios_criticos: list[str]) -> set[str]:
    """Garante 1 a 3 críticos válidos ('tecnicas' como default seguro)."""
    validos = [c for c in criterios_criticos if c in IDS]
    if not validos:
        return {"tecnicas"}
    return set(validos[:3])


def montar_regua(proposta: ReguaPropostaLLM) -> Regua:
    """Transforma a proposta do LLM em `Regua` válida (Python, determinístico)."""
    pesos = _renormalizar_pesos(proposta.pesos_sugeridos)
    criticos = _selecionar_criticos(proposta.criterios_criticos)

    criterios = [
        CriterioRegua(
            id=cid,
            rotulo=ROTULOS_CRITERIOS[cid],
            peso=pesos[cid],
            e_critico=cid in criticos,
            nota_minima=NOTA_MINIMA_PADRAO,
        )
        for cid in IDS
    ]
    volatilidades = [
        VolatilidadeCompetencia(competencia=comp, volatilidade=volatilidade_de(comp))
        for comp in proposta.competencias_detectadas
    ]
    th = cfg_rt.obter_thresholds_default()
    thresholds = Thresholds(
        corte_verde=th.get("corte_verde", 60),
        corte_amarelo=th.get("corte_amarelo", 35),
        alvo_auto_decisao=th.get("alvo_auto_decisao", 0.65),
    )
    return Regua(
        criterios=criterios,
        knockouts=proposta.knockouts,
        volatilidades=volatilidades,
        thresholds=thresholds,
        congelada=False,
    )


async def propor_regua(cliente: ClienteLLM, descricao_vaga: str) -> Regua:
    """Lê a descrição da vaga e devolve uma régua proposta (não congelada)."""
    skill = contratos_skill.sistema("skill_regua")
    # A régua é uma extração estruturada interativa: desligamos o raciocínio
    # estendido (rápido e confiável, evita estouro de timeout em descrições
    # longas) e damos uma folga de tempo maior, dentro do limite do front (120s).
    proposta = await cliente.extrair(
        skill_text=skill,
        conteudo=f"Descrição da vaga:\n{descricao_vaga}",
        schema=ReguaPropostaLLM,
        estagio="regua",
        max_tokens=2048,
        usar_thinking=False,
        timeout_override=110.0,
    )
    return montar_regua(proposta)
