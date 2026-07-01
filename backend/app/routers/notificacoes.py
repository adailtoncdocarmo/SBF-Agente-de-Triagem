"""Endpoints de Notificações (sino) — disparadas ao concluir um lote."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models_db import Notificacao
from app.texto import limpar_dashes

router = APIRouter(tags=["notificacoes"])


class NotificacaoResposta(BaseModel):
    id: int
    lote_id: int
    lida: bool
    payload: dict
    # Quando a notificação foi criada (o sino exibe data/hora ao RH).
    criado_em: datetime | None = None


def _para_resposta(n: Notificacao) -> NotificacaoResposta:
    # Limpa travessões do texto (inclui notificações antigas já salvas no banco).
    payload = dict(n.payload_json)
    if isinstance(payload.get("titulo"), str):
        payload["titulo"] = limpar_dashes(payload["titulo"])
    if isinstance(payload.get("mensagem"), str):
        payload["mensagem"] = limpar_dashes(payload["mensagem"])
    return NotificacaoResposta(
        id=n.id,
        lote_id=n.lote_id,
        lida=n.lida,
        payload=payload,
        criado_em=n.criado_em,
    )


@router.get("/notificacoes", response_model=list[NotificacaoResposta])
def listar_notificacoes(db: Session = Depends(get_db)) -> list[NotificacaoResposta]:
    """Central de notificações (mais recentes primeiro)."""
    itens = db.scalars(select(Notificacao).order_by(Notificacao.criado_em.desc()))
    return [_para_resposta(n) for n in itens]


@router.put("/notificacoes/{notificacao_id}/lida", response_model=NotificacaoResposta)
def marcar_lida(notificacao_id: int, db: Session = Depends(get_db)) -> NotificacaoResposta:
    """Marca uma notificação como lida."""
    notif = db.get(Notificacao, notificacao_id)
    if notif is None:
        raise HTTPException(status_code=404, detail="Notificação não encontrada.")
    notif.lida = True
    db.commit()
    return _para_resposta(notif)
