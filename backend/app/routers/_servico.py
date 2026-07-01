"""Helpers de leitura compartilhados pelos routers de lotes e avaliações."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models_db import Candidato, Lote
from app.schemas.avaliacao import Avaliacao
from app.schemas.enums import StatusCandidato
from app.schemas.saidas import FalhaCandidato
from app.triagem.ficha import chave_ordenacao


def carregar_avaliacoes_concluidas(
    db: Session, lote_id: int
) -> list[tuple[int, str, Avaliacao]]:
    """Lista `(candidato_id, nome_arquivo, Avaliacao)` dos CVs concluídos do lote."""
    candidatos = db.scalars(
        select(Candidato).where(
            Candidato.lote_id == lote_id,
            Candidato.status == StatusCandidato.CONCLUIDO.value,
        )
    )
    itens: list[tuple[int, str, Avaliacao]] = []
    for c in candidatos:
        if c.avaliacao is None:
            continue
        itens.append((c.id, c.nome_arquivo, Avaliacao.model_validate(c.avaliacao.avaliacao_json)))
    return itens


def carregar_avaliacoes_da_vaga(
    db: Session, vaga_id: int
) -> list[tuple[int, str, str | None, Avaliacao]]:
    """Lista `(candidato_id, nome_arquivo, nome_candidato, Avaliacao)` da vaga.

    É o pool acumulado: junta os candidatos de todos os lotes da vaga, para
    ranquear e calibrar a população inteira (subir um 2º lote reposiciona o 1º).
    """
    candidatos = db.scalars(
        select(Candidato)
        .join(Lote, Candidato.lote_id == Lote.id)
        .where(
            Lote.vaga_id == vaga_id,
            Candidato.status == StatusCandidato.CONCLUIDO.value,
        )
    )
    itens: list[tuple[int, str, str | None, Avaliacao]] = []
    for c in candidatos:
        if c.avaliacao is None:
            continue
        itens.append(
            (
                c.id,
                c.nome_arquivo,
                c.nome_candidato,
                Avaliacao.model_validate(c.avaliacao.avaliacao_json),
            )
        )
    return itens


def carregar_falhas_da_vaga(db: Session, vaga_id: int) -> list[FalhaCandidato]:
    """Lista os currículos da vaga que falharam no processamento (status erro)."""
    candidatos = db.scalars(
        select(Candidato)
        .join(Lote, Candidato.lote_id == Lote.id)
        .where(
            Lote.vaga_id == vaga_id,
            Candidato.status == StatusCandidato.ERRO.value,
        )
    )
    return [
        FalhaCandidato(
            candidato_id=c.id,
            id_anonimo=c.id_anonimo,
            nome_arquivo=c.nome_arquivo,
            nome_candidato=c.nome_candidato,
            motivo=c.erro or "Erro desconhecido no processamento.",
        )
        for c in candidatos
    ]


def contar_avaliados_da_vaga(db: Session, vaga_id: int) -> int:
    """Conta candidatos concluídos (avaliados) acumulados na vaga."""
    return (
        db.scalar(
            select(func.count(Candidato.id))
            .join(Lote, Candidato.lote_id == Lote.id)
            .where(
                Lote.vaga_id == vaga_id,
                Candidato.status == StatusCandidato.CONCLUIDO.value,
            )
        )
        or 0
    )


def ordenar(itens: list[tuple[int, str, Avaliacao]]) -> list[tuple[int, str, Avaliacao]]:
    """Ordena pelos critérios de desempate da Parte 6.6 (score → críticos → …)."""
    return sorted(itens, key=lambda it: chave_ordenacao(it[2]))
