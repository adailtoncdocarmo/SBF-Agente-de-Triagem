"""Pacote de triagem — pipeline neurossimbólico do Framework v3.

Organização:
    - Estágios determinísticos (Python puro, testáveis): `cegamento`, `portao2`,
      `score`, `calibracao`, `zonas`, `ficha`.
    - Estágios de julgamento (LLM): `agente_regua`, `estagios` (Portão 1, scoring,
      flags, desempate), via o wrapper único `cliente_claude`.
    - Orquestração: `orquestrador` encadeia per-CV → lote-level; `fila` é o worker
      assíncrono in-process.

Princípio: a IA só extrai sinais; o Python aplica portões, calcula score, calibra
o lote e separa o que a IA decide do que vai para o humano.
"""

from __future__ import annotations
