"""Carregamento do benchmark sintético (LGPD-safe) da camada de avaliação.

O benchmark vive em `backend/data/benchmark/`: uma vaga com régua congelada,
currículos sintéticos (sem PII real), gabarito humano indicativo e pares de viés.
Roda separado do fluxo de triagem (que usa CVs reais do usuário).
"""

from __future__ import annotations

import json
from pathlib import Path

from app.schemas.regua import Regua

_DIR_BENCHMARK = Path(__file__).resolve().parents[2] / "data" / "benchmark"


def carregar_vaga() -> tuple[str, Regua]:
    """Retorna `(titulo, Regua congelada)` da vaga do benchmark."""
    dados = json.loads((_DIR_BENCHMARK / "vaga.json").read_text(encoding="utf-8"))
    return dados["titulo"], Regua.model_validate(dados["regua"])


def carregar_descricao_vaga() -> str:
    """Texto descritivo da vaga do benchmark (amostra para testar a skill de régua)."""
    dados = json.loads((_DIR_BENCHMARK / "vaga.json").read_text(encoding="utf-8"))
    return dados.get("descricao") or dados.get("titulo", "")


def carregar_curriculos() -> dict[str, str]:
    """Retorna `{nome_arquivo: texto_bruto}` dos currículos sintéticos."""
    dir_cv = _DIR_BENCHMARK / "curriculos"
    return {
        caminho.name: caminho.read_text(encoding="utf-8")
        for caminho in sorted(dir_cv.glob("*.txt"))
    }


def carregar_gabarito() -> tuple[dict[str, str], list[dict]]:
    """Retorna `(gabarito, pares_vies)` do benchmark."""
    dados = json.loads((_DIR_BENCHMARK / "gabarito.json").read_text(encoding="utf-8"))
    return dados["gabarito"], dados.get("pares_vies", [])


def benchmark_existe() -> bool:
    """True se as fixtures do benchmark estão presentes."""
    return (_DIR_BENCHMARK / "vaga.json").is_file()
