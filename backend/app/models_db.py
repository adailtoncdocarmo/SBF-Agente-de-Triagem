"""Modelos ORM (SQLAlchemy 2.0) — persistência da triagem.

Estratégia de mapeamento: a `Regua` e a `Avaliacao` (schemas Pydantic ricos)
são guardadas como colunas `JSON`; os escalares usados para filtrar/ordenar/
ranquear (`status`, `score_final`, `zona`, contagens) são promovidos a colunas
tipadas. A conversão Pydantic↔ORM é explícita nos serviços:
    leitura  → `Regua.model_validate(vaga.regua_json)`
    escrita  → `vaga.regua_json = regua.model_dump(mode="json")`

`criar_tabelas()` (em `database.py`) já importa este módulo e roda
`Base.metadata.create_all` — declarar os modelos aqui basta.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Vaga(Base):
    """Uma vaga com sua régua (rubrica ponderada). Congelada antes de triar."""

    __tablename__ = "vagas"

    id: Mapped[int] = mapped_column(primary_key=True)
    titulo: Mapped[str] = mapped_column(String, nullable=False)
    descricao: Mapped[str] = mapped_column(String, nullable=False)
    regua_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    congelada: Mapped[bool] = mapped_column(default=False)
    # Status visível ao RH: só dois valores — "ativa" (default) ou "arquivada".
    # (Distinto de `congelada`, que é interno: a régua foi fechada para triar.)
    status: Mapped[str] = mapped_column(String, default="ativa", index=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    lotes: Mapped[list["Lote"]] = relationship(
        back_populates="vaga", cascade="all, delete-orphan"
    )


class Lote(Base):
    """Um lote de currículos triados contra uma vaga."""

    __tablename__ = "lotes"

    id: Mapped[int] = mapped_column(primary_key=True)
    vaga_id: Mapped[int] = mapped_column(
        ForeignKey("vagas.id"), index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String, default="enfileirado", index=True)
    total: Mapped[int] = mapped_column(Integer, default=0)
    concluidos: Mapped[int] = mapped_column(Integer, default=0)
    n_entra: Mapped[int] = mapped_column(Integer, default=0)
    n_avaliar: Mapped[int] = mapped_column(Integer, default=0)
    n_cai: Mapped[int] = mapped_column(Integer, default=0)
    taxa_auto_decisao: Mapped[float | None] = mapped_column(Float, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    concluido_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    vaga: Mapped["Vaga"] = relationship(back_populates="lotes")
    candidatos: Mapped[list["Candidato"]] = relationship(
        back_populates="lote", cascade="all, delete-orphan"
    )


class Candidato(Base):
    """Um currículo dentro de um lote.

    A **IA recebe só o `texto_cegado`** (sem PII). O **arquivo original**
    (`arquivo_original`/`arquivo_mime`) é guardado à parte para o RH autorizado
    visualizar o CV na ficha — nunca é enviado à IA.
    """

    __tablename__ = "candidatos"

    id: Mapped[int] = mapped_column(primary_key=True)
    lote_id: Mapped[int] = mapped_column(
        ForeignKey("lotes.id"), index=True, nullable=False
    )
    nome_arquivo: Mapped[str] = mapped_column(String, nullable=False)
    # Nome do candidato (rótulo de exibição ao RH). Capturado no cegamento; a IA
    # nunca o recebe (scoring cego). Pode ser None quando não detectado no CV.
    nome_candidato: Mapped[str | None] = mapped_column(String, nullable=True)
    hash_cv: Mapped[str] = mapped_column(String, index=True, nullable=False)
    id_anonimo: Mapped[str] = mapped_column(String, nullable=False)
    texto_cegado: Mapped[str | None] = mapped_column(String, nullable=True)
    # Arquivo original (PDF/TXT) para visualização humana — não vai para a IA.
    arquivo_original: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    arquivo_mime: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="enfileirado", index=True)
    estagio_atual: Mapped[str | None] = mapped_column(String, nullable=True)
    erro: Mapped[str | None] = mapped_column(String, nullable=True)
    score_final: Mapped[float | None] = mapped_column(Float, nullable=True)
    zona: Mapped[str | None] = mapped_column(String, nullable=True)

    lote: Mapped["Lote"] = relationship(back_populates="candidatos")
    avaliacao: Mapped["Avaliacao | None"] = relationship(
        back_populates="candidato", uselist=False, cascade="all, delete-orphan"
    )


class Avaliacao(Base):
    """A avaliação rastreável de um candidato (schema Pydantic serializado)."""

    __tablename__ = "avaliacoes"

    id: Mapped[int] = mapped_column(primary_key=True)
    candidato_id: Mapped[int] = mapped_column(
        ForeignKey("candidatos.id"), unique=True, index=True, nullable=False
    )
    avaliacao_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    score_final: Mapped[float] = mapped_column(Float, default=0.0)
    zona: Mapped[str | None] = mapped_column(String, nullable=True)
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    candidato: Mapped["Candidato"] = relationship(back_populates="avaliacao")


class Notificacao(Base):
    """Notificação in-app (sino) — disparada ao concluir um lote."""

    __tablename__ = "notificacoes"

    id: Mapped[int] = mapped_column(primary_key=True)
    lote_id: Mapped[int] = mapped_column(
        ForeignKey("lotes.id"), index=True, nullable=False
    )
    lida: Mapped[bool] = mapped_column(default=False)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class RegistroCusto(Base):
    """Telemetria por chamada de API — alimenta /api/metricas e a avaliação."""

    __tablename__ = "custos"

    id: Mapped[int] = mapped_column(primary_key=True)
    lote_id: Mapped[int | None] = mapped_column(
        ForeignKey("lotes.id"), index=True, nullable=True
    )
    candidato_id: Mapped[int | None] = mapped_column(
        ForeignKey("candidatos.id"), nullable=True
    )
    estagio: Mapped[str] = mapped_column(String, nullable=False)
    provedor: Mapped[str] = mapped_column(String, default="anthropic")
    modelo: Mapped[str] = mapped_column(String, nullable=False)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    tokens_cache_read: Mapped[int] = mapped_column(Integer, default=0)
    custo_usd: Mapped[float] = mapped_column(Float, default=0.0)
    latencia_ms: Mapped[int] = mapped_column(Integer, default=0)
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ConfiguracaoRuntime(Base):
    """Configuração editável em runtime (low-code) — sobrepõe-se ao `.env`/código.

    Store key/value: a `chave` é o nome da configuração (ex.: 'anthropic_api_key',
    'modelo_scoring', 'fallback') e `valor_json` o valor (string, número, bool ou dict).
    """

    __tablename__ = "configuracoes_runtime"

    chave: Mapped[str] = mapped_column(String, primary_key=True)
    valor_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
