"""Camada de banco de dados — engine SQLAlchemy (SQLite), Base e dependência `get_db`.

SQLite mantém o princípio "roda em qualquer máquina" (arquivo local, sem servidor).
A migração futura para PostgreSQL é trivial: basta trocar a `database_url`,
pois todo o acesso passa pelo ORM.
"""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import configuracoes

# `check_same_thread=False` é necessário para o SQLite servir múltiplas
# requisições do FastAPI dentro do mesmo processo.
engine = create_engine(
    configuracoes.database_url,
    connect_args={"check_same_thread": False},
)


@event.listens_for(Engine, "connect")
def _configurar_sqlite(dbapi_connection, _connection_record) -> None:
    """Liga WAL e foreign keys no SQLite (melhor concorrência com a fila async).

    WAL permite leituras concorrentes com uma escrita — importante porque o
    worker assíncrono escreve enquanto os routers leem o status do lote.
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base declarativa de todos os modelos ORM (definidos na Fase 2)."""


def criar_tabelas() -> None:
    """Cria o arquivo SQLite e as tabelas registradas na `Base`.

    Na Fase 1 não há modelos de negócio, então isto apenas garante que o
    arquivo do banco exista. Os modelos entram na Fase 2 em `models_db.py`.
    """
    # Garante que o diretório de dados exista antes de criar o arquivo.
    configuracoes.db_path.parent.mkdir(parents=True, exist_ok=True)
    # Import tardio: registra os modelos na metadata da Base, se houver.
    from app import models_db  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _migrar_colunas_novas()


def _migrar_colunas_novas() -> None:
    """Migração leve (sem Alembic): adiciona colunas novas em bancos já existentes.

    `create_all` não altera tabelas já criadas; aqui garantimos, de forma
    idempotente, que colunas adicionadas depois (ex.: `nome_candidato`) existam.
    """
    from sqlalchemy import text

    colunas_esperadas = {
        "candidatos": [
            ("nome_candidato", "VARCHAR"),
            ("arquivo_original", "BLOB"),
            ("arquivo_mime", "VARCHAR"),
        ],
        # `status` da vaga (ativa/arquivada): bancos antigos recebem 'ativa' nas
        # linhas existentes via o DEFAULT do ALTER TABLE.
        "vagas": [
            ("status", "VARCHAR DEFAULT 'ativa'"),
        ],
    }
    with engine.begin() as conexao:
        for tabela, colunas in colunas_esperadas.items():
            existentes = {
                linha[1]
                for linha in conexao.execute(text(f"PRAGMA table_info({tabela})"))
            }
            for nome, tipo in colunas:
                if nome not in existentes:
                    conexao.execute(text(f"ALTER TABLE {tabela} ADD COLUMN {nome} {tipo}"))


def get_db() -> Generator[Session, None, None]:
    """Dependência do FastAPI: fornece uma sessão e a fecha ao final."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
