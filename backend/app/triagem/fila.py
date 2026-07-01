"""Fila assíncrona in-process (sem Celery/Redis — fiel ao "só a chave de API").

Um worker `asyncio` consome lotes da fila e os processa pelo orquestrador. O
estado é persistido no SQLite a cada etapa, então a fila é **retomável**: ao
reiniciar, o `lifespan` re-enfileira os lotes pendentes e os CVs já prontos são
pulados.
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from app.database import SessionLocal
from app.models_db import Lote
from app.schemas.enums import StatusLote
from app.triagem.orquestrador import processar_lote

logger = logging.getLogger("triagem.fila")


class FilaTriagem:
    """Fila in-process com um único worker assíncrono."""

    def __init__(self) -> None:
        # A Queue é criada em `iniciar()` (no loop em execução) — não no import,
        # para não ficar presa a um event loop diferente (ex.: múltiplos TestClient).
        self._queue: asyncio.Queue[int] | None = None
        self._worker: asyncio.Task[None] | None = None

    def _garantir_queue(self) -> asyncio.Queue[int]:
        if self._queue is None:
            self._queue = asyncio.Queue()
        return self._queue

    async def iniciar(self) -> None:
        """Sobe o worker e re-enfileira lotes pendentes (retomada)."""
        self._queue = asyncio.Queue()  # fila nova, ligada ao loop atual
        if self._worker is None or self._worker.done():
            self._worker = asyncio.create_task(self._consumir())
        await self._reenfileirar_pendentes()

    async def enfileirar(self, lote_id: int) -> None:
        await self._garantir_queue().put(lote_id)

    async def parar(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            try:
                await self._worker
            except asyncio.CancelledError:
                pass
            self._worker = None

    async def _consumir(self) -> None:
        fila = self._garantir_queue()
        while True:
            lote_id = await fila.get()
            try:
                await processar_lote(lote_id)
            except asyncio.CancelledError:
                raise
            except Exception:  # falha de um lote nunca derruba o worker
                logger.exception("Falha ao processar lote %s; marcando erro.", lote_id)
                self._marcar_lote_erro(lote_id)
            finally:
                fila.task_done()

    async def _reenfileirar_pendentes(self) -> None:
        with SessionLocal() as sessao:
            pendentes = list(
                sessao.scalars(
                    select(Lote.id).where(
                        Lote.status.in_(
                            [StatusLote.ENFILEIRADO.value, StatusLote.PROCESSANDO.value]
                        )
                    )
                )
            )
        fila = self._garantir_queue()
        for lote_id in pendentes:
            logger.info("Retomando lote pendente %s", lote_id)
            await fila.put(lote_id)

    @staticmethod
    def _marcar_lote_erro(lote_id: int) -> None:
        try:
            with SessionLocal() as sessao:
                lote = sessao.get(Lote, lote_id)
                if lote is not None:
                    lote.status = StatusLote.ERRO.value
                    sessao.commit()
        except Exception:
            logger.exception("Não foi possível marcar erro do lote %s.", lote_id)


# Instância única usada pelo app e pelos routers.
fila = FilaTriagem()
