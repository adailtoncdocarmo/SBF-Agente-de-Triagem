"""Tabela estática competência → volatilidade (anti-drift, Framework 2.2).

Decisão de projeto: NÃO pedimos ao LLM para reclassificar a volatilidade a cada
execução (isso seria mais uma fonte de variância). Mantemos uma tabela estática
por domínio (aqui: varejo BR) e casamos por palavra-chave. Default = média.
"""

from __future__ import annotations

import unicodedata

from app.schemas.enums import Volatilidade

# Palavras-chave por volatilidade (sem acento, minúsculas).
_ALTA = {
    "e-commerce", "ecommerce", "marketplace", "redes sociais", "midias sociais",
    "app", "aplicativo", "crm digital", "ferramentas digitais", "trafego pago",
    "marketing digital", "vendas online", "omnichannel",
}
_MEDIA = {
    "pdv", "sistema pdv", "frente de caixa", "erp", "excel", "planilhas",
    "estoque", "logistica", "fiscal", "nota fiscal", "sap", "power bi",
    "gestao de estoque", "controle de caixa", "tef",
}
_BAIXA = {
    "atendimento", "atendimento ao cliente", "vendas", "negociacao",
    "comunicacao", "lideranca", "trabalho em equipe", "organizacao",
    "proatividade", "relacionamento", "relacionamento com o cliente",
    "pos-venda", "abordagem", "persuasao", "empatia", "resolucao de conflitos",
    "gestao de pessoas", "rotina de loja",
}


def _normalizar(texto: str) -> str:
    """Minúsculas + remoção de acentos para casar com a tabela."""
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)
    )
    return sem_acento.lower().strip()


def volatilidade_de(competencia: str) -> Volatilidade:
    """Classifica a volatilidade de uma competência via tabela estática.

    Casa por substring (a competência extraída pode ser uma frase). Default:
    média — o caso mais comum em varejo (ferramentas e processos operacionais).
    """
    norm = _normalizar(competencia)
    for chave in _ALTA:
        if chave in norm:
            return Volatilidade.ALTA
    for chave in _BAIXA:
        if chave in norm:
            return Volatilidade.BAIXA
    for chave in _MEDIA:
        if chave in norm:
            return Volatilidade.MEDIA
    return Volatilidade.MEDIA
