"""Fixtures do benchmark sintético (LGPD-safe) de currículos e vaga.

    - `dataset.py` carrega o benchmark de `backend/data/benchmark/`, usado pelos
      testes (ex.: `test_contratos_skill`). Não há camada de avaliação/benchmark
      rodável — as métricas de qualidade (consistência, κ, paridade) são roadmap,
      com o benchmark + pares de viés como base metodológica.
"""
