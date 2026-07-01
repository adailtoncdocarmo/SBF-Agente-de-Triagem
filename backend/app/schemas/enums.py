"""Enums e tipos compartilhados do domínio de triagem (Framework v3).

Centraliza os vocabulários controlados que cruzam fronteiras de módulo. Tudo em
`str, Enum` para serializar como string no JSON e no SQLite sem conversão extra.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

# Identificadores semânticos dos 7 critérios canônicos (sempre os mesmos).
CriterioId = Literal[
    "tecnicas",
    "experiencia",
    "resultados",
    "complexidade",
    "setor",
    "formacao",
    "progressao",
]

# Rótulos legíveis de cada critério (para fichas e UI).
ROTULOS_CRITERIOS: dict[str, str] = {
    "tecnicas": "Competências técnicas essenciais",
    "experiencia": "Experiência profissional relevante",
    "resultados": "Resultados e impacto",
    "complexidade": "Senioridade e complexidade",
    "setor": "Aderência ao setor e contexto",
    "formacao": "Formação e certificações",
    "progressao": "Progressão e coerência de carreira",
}


class EstadoKnockout(str, Enum):
    """Portão 1 — knockout em três estados (Framework 6.2)."""

    ATENDE = "atende"
    NAO_ATENDE = "nao_atende"  # única que bloqueia automaticamente
    NAO_EVIDENCIADO = "nao_evidenciado"  # nunca reprova sozinho → validação


class StatusCritico(str, Enum):
    """Portão 2 — gating de mínimos nos críticos (Framework 6.3)."""

    APROVADO = "aprovado"
    REPROVADO = "reprovado"  # nota < piso COM evidência → sai do ranking
    VALIDACAO = "validacao"  # nota baixa por FALTA de evidência → zona humana
    NAO_APLICAVEL = "nao_aplicavel"  # critério não é crítico nesta vaga


class ZonaDecisao(str, Enum):
    """As três zonas de decisão (Framework Parte 1.3)."""

    ENTRA = "entra"  # auto-shortlist — IA decide
    AVALIAR = "avaliar"  # meio ambíguo — humano decide
    CAI = "cai"  # auto-descarte — IA decide


class Recomendacao(str, Enum):
    """Recomendação final exibida ao RH (mapeia 1:1 com a zona)."""

    AVANCAR = "avancar"
    AVALIAR = "avaliar"
    NAO_AVANCAR = "nao_avancar"


class Confianca(str, Enum):
    """Confiança da avaliação (modula roteamento, não a nota)."""

    ALTA = "alta"
    MEDIA = "media"
    BAIXA = "baixa"


class Severidade(str, Enum):
    """Severidade de uma flag de risco (Framework 4.1)."""

    BAIXA = "baixa"
    MEDIA = "media"
    ALTA = "alta"
    CRITICA = "critica"


class Volatilidade(str, Enum):
    """Volatilidade de uma competência → regra de recência (Framework 2.2)."""

    ALTA = "alta"  # decai sem uso em ~24-36 meses
    MEDIA = "media"  # decai sem uso em ~5 anos
    BAIXA = "baixa"  # não decai automaticamente


class StatusLote(str, Enum):
    """Estado de um lote de currículos na fila."""

    ENFILEIRADO = "enfileirado"
    PROCESSANDO = "processando"
    CONCLUIDO = "concluido"
    ERRO = "erro"


class StatusCandidato(str, Enum):
    """Estado de um candidato individual dentro do lote."""

    ENFILEIRADO = "enfileirado"
    PROCESSANDO = "processando"
    AGUARDANDO_LOTE = "aguardando_lote"  # estágios per-CV ok; espera lote-level
    CONCLUIDO = "concluido"
    ERRO = "erro"


class EstagioCandidato(str, Enum):
    """Último estágio per-CV concluído (permite retomada após restart)."""

    PENDENTE = "pendente"
    CEGAMENTO = "cegamento"
    PORTAO1 = "portao1"
    SCORING = "scoring"
    FLAGS = "flags"
    PORTAO2 = "portao2"
    SCORE = "score"
    CONCLUIDO = "concluido"
