"""Endpoint de saúde — verifica que a API está de pé."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    """Retorna o status da API.

    Usado pelo teste de fumaça e por health checks (Docker/orquestrador).
    """
    return {"status": "ok"}
