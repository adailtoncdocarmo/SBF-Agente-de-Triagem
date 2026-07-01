"""Fixtures e construtores compartilhados pelos testes determinísticos."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from app.schemas import (
    Confianca,
    CriterioRegua,
    NotaCriterioLLM,
    ROTULOS_CRITERIOS,
    Regua,
    SaidaScoringLLM,
    Thresholds,
    VolatilidadeCompetencia,
)

IDS = ["tecnicas", "experiencia", "resultados", "complexidade", "setor", "formacao", "progressao"]


@pytest.fixture(autouse=True, scope="session")
def _banco_isolado_para_testes():
    """Isola os testes num banco descartável (NUNCA toca o `app.db` real).

    Antes desta isolação, os testes de configuração apagavam a chave de API salva
    pelo usuário e os de pipeline poluíam as Vagas com dados de teste — porque
    `SessionLocal`/`criar_tabelas` apontavam para o banco de produção. Aqui
    reconfiguramos o engine para um SQLite temporário; como `SessionLocal` é um
    `sessionmaker` mutado in-place, todos os módulos que já o importaram passam a
    usar o banco de teste sem alteração.
    """
    import app.database as database

    diretorio = tempfile.mkdtemp(prefix="sbf-test-db-")
    arquivo = Path(diretorio) / "test.db"
    engine_teste = create_engine(
        f"sqlite:///{arquivo}", connect_args={"check_same_thread": False}
    )

    engine_original = database.engine
    database.engine = engine_teste
    database.SessionLocal.configure(bind=engine_teste)
    database.configuracoes.db_path = arquivo  # coerência p/ quem lê db_path
    database.criar_tabelas()

    yield

    database.SessionLocal.configure(bind=engine_original)
    database.engine = engine_original
    engine_teste.dispose()
    shutil.rmtree(diretorio, ignore_errors=True)

# Pesos da partição Operacional (Framework 5.2) — somam 100.
PESOS_OPERACIONAL = {"tecnicas": 25, "experiencia": 30, "resultados": 8, "complexidade": 7, "setor": 10, "formacao": 15, "progressao": 5}


def construir_regua(
    *,
    criticos: tuple[str, ...] = ("tecnicas", "experiencia"),
    pisos: dict[str, int] | None = None,
    volatilidades: list[VolatilidadeCompetencia] | None = None,
    thresholds: Thresholds | None = None,
) -> Regua:
    """Constrói uma régua operacional/pleno válida para os testes."""
    pisos = pisos or {}
    criterios = [
        CriterioRegua(
            id=cid,
            rotulo=ROTULOS_CRITERIOS[cid],
            peso=PESOS_OPERACIONAL[cid],
            e_critico=cid in criticos,
            nota_minima=pisos.get(cid, 2),
        )
        for cid in IDS
    ]
    return Regua(
        criterios=criterios,
        volatilidades=volatilidades or [],
        thresholds=thresholds or Thresholds(),
    )


def construir_notas(
    notas: dict[str, int],
    *,
    com_evidencia: bool = True,
    confianca: Confianca = Confianca.ALTA,
    ultimo_uso_ano: int | None = None,
) -> SaidaScoringLLM:
    """Constrói uma `SaidaScoringLLM` a partir de um mapa id→nota."""
    return SaidaScoringLLM(
        notas=[
            NotaCriterioLLM(
                criterio=cid,
                nota_0_4=n,
                evidencias=["evidência concreta"] if com_evidencia else [],
                lacunas=[] if n >= 3 else ["lacuna observada"],
                ultimo_uso_ano=ultimo_uso_ano,
                confianca_criterio=confianca,
            )
            for cid, n in notas.items()
        ]
    )
