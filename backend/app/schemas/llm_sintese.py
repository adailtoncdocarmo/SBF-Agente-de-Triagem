"""Schema da saída da Síntese (estágio 9) — LLM-facing.

A IA recebe a avaliação JÁ PRONTA (notas, zona, evidências, lacunas, flags) e
escreve dois textos curtos e objetivos para o RH: por que o candidato adere (ou
não) ao perfil e o que fazer a seguir. A IA **não recalcula nada** — só redige a
partir dos sinais que já existem. Os textos têm no máximo ~3 linhas cada.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SaidaSinteseLLM(BaseModel):
    """Textos enriquecidos da ficha (aderência + recomendação).

    Sem `max_length` rígido: um limite duro fazia a validação falhar quando o
    modelo escrevia um pouco mais que o teto (e a ficha caía no texto de
    template). O tamanho é controlado pelo prompt e por truncação defensiva no
    Python ao gravar.
    """

    aderencia: str = Field(
        default="",
        description="Leitura do fit do candidato ao perfil — objetiva, ~2-3 linhas.",
    )
    recomendacao: str = Field(
        default="",
        description="Orientação acionável ao RH (próximos passos, o que validar) — ~2-3 linhas.",
    )
