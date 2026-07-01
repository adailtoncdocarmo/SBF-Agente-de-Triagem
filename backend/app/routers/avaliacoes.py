"""Endpoint de Avaliações — a ficha rastreável de um candidato."""

from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models_db import Candidato
from app.schemas.avaliacao import Avaliacao
from app.schemas.saidas import FichaCandidato
from app.routers._servico import carregar_avaliacoes_concluidas, ordenar
from app.triagem.ficha import montar_ficha

router = APIRouter(tags=["avaliacoes"])


# Rota mais específica primeiro (defensivo) — visualização do currículo original.
@router.get("/avaliacoes/{candidato_id}/cv")
def obter_cv(candidato_id: int, db: Session = Depends(get_db)) -> Response:
    """Devolve o arquivo original do currículo (PDF/TXT/DOCX) para o RH visualizar.

    O original é guardado só para visualização humana; a IA nunca o recebe.
    """
    candidato = db.get(Candidato, candidato_id)
    if candidato is None or not candidato.arquivo_original:
        raise HTTPException(status_code=404, detail="Currículo original indisponível.")
    mime = candidato.arquivo_mime or "application/octet-stream"
    # `inline` para abrir no visualizador do navegador (iframe), não baixar.
    # O nome vem do upload (não confiável): codifica via RFC 5987 (`filename*`)
    # para impedir injeção de header por aspas/quebras de linha no nome do arquivo.
    nome = candidato.nome_arquivo or f"cv-{candidato_id}"
    return Response(
        content=candidato.arquivo_original,
        media_type=mime,
        headers={"Content-Disposition": f"inline; filename*=UTF-8''{quote(nome)}"},
    )


@router.get("/avaliacoes/{candidato_id}", response_model=FichaCandidato)
def obter_ficha(candidato_id: int, db: Session = Depends(get_db)) -> FichaCandidato:
    """Ficha completa de um candidato (aderência, destaques, lacunas, breakdown)."""
    candidato = db.get(Candidato, candidato_id)
    if candidato is None or candidato.avaliacao is None:
        raise HTTPException(status_code=404, detail="Avaliação não encontrada.")

    avaliacao = Avaliacao.model_validate(candidato.avaliacao.avaliacao_json)

    # Posição no lote (ordenação por desempate da Parte 6.6).
    ordenados = ordenar(carregar_avaliacoes_concluidas(db, candidato.lote_id))
    total = len(ordenados)
    posicao = next(
        (i for i, (cid, _, _) in enumerate(ordenados, start=1) if cid == candidato_id),
        None,
    )

    ficha = montar_ficha(
        candidato_id=candidato.id,
        nome_arquivo=candidato.nome_arquivo,
        avaliacao=avaliacao,
        posicao=posicao,
        total_lote=total or None,
        nome_candidato=candidato.nome_candidato,
    )
    # Só há "Ver currículo" quando o original foi guardado (envios recentes).
    ficha.cv_disponivel = candidato.arquivo_original is not None
    return ficha
