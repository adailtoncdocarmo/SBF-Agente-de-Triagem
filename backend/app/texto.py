"""Higiene de texto exibido ao RH: remove travessões usados como pontuação.

Aplicado na MONTAGEM das respostas (ficha, ranking, notificações) — limpa tanto
o texto gerado pela IA quanto dados já salvos, sem alterar o que está no banco.
O RH pediu textos limpos, sem o travessão "—" no meio das frases.
"""

from __future__ import annotations


def limpar_dashes(s: str | None) -> str:
    """Troca travessões (— e –) por pontuação simples, deixando o texto limpo."""
    if not s:
        return s or ""
    return (
        s.replace(" — ", ", ")
        .replace(" – ", ", ")
        .replace("—", ", ")
        .replace("–", "-")
    )
