"""Carregador de skills — progressive disclosure determinístico.

Cada "skill" é uma fatia focada do Framework v3, em markdown, carregada só no seu
estágio (o orquestrador escolhe — não o agente). Carregar só o pedaço relevante
reduz contexto e drift, e o texto estável é cacheado pelo `cliente_claude`.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

_DIR_SKILLS = Path(__file__).resolve().parent / "skills"


@lru_cache
def carregar_skill(nome: str) -> str:
    """Lê o conteúdo de `skills/{nome}.md` (cacheado em memória)."""
    caminho = _DIR_SKILLS / f"{nome}.md"
    if not caminho.is_file():
        raise FileNotFoundError(f"Skill não encontrada: {caminho}")
    return caminho.read_text(encoding="utf-8")
