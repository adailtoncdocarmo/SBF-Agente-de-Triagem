"""Ponto de entrada do FastAPI.

Responsabilidades:
    - Cria o app e inclui os routers da API sob o prefixo `/api`.
    - Serve o frontend React buildado (`frontend/dist`) na raiz `/`,
      com *fallback* de SPA (deep-links do React Router funcionam no refresh).
    - No startup, cria o arquivo SQLite e as tabelas (vazias na Fase 1).

Um único processo serve API + frontend → o avaliador não precisa de Node
para rodar, apenas para desenvolver.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator, Awaitable, Callable

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from app.config import configuracoes
from app.database import criar_tabelas
from app.routers import (
    avaliacoes,
    configuracao,
    health,
    lotes,
    metricas,
    notificacoes,
    vagas,
)
from app.triagem.fila import fila


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Ciclo de vida do app: cria o banco, sobe a fila e retoma pendências."""
    criar_tabelas()
    await fila.iniciar()  # sobe o worker e re-enfileira lotes pendentes
    try:
        yield
    finally:
        await fila.parar()


app = FastAPI(
    title="SBF · Agente de Triagem de Currículos",
    description=(
        "Esqueleto (Fase 1) do agente de triagem de candidatos para "
        "operações de varejo — Case Grupo SBF."
    ),
    version="0.1.0",
    lifespan=lifespan,
)


# --- Hardening (demo) ---------------------------------------------------------
# Teto de tamanho do corpo da requisição: deriva dos limites de upload (nº de
# arquivos × tamanho por arquivo) com folga para o overhead do multipart. É
# cinto-e-suspensório: o router de lotes já valida arquivo a arquivo; isto
# barra um corpo gigante antes mesmo de começar a ler.
_MAX_CORPO_BYTES = int(
    configuracoes.max_arquivos_por_lote
    * configuracoes.max_tamanho_arquivo_mb
    * 1024
    * 1024
    * 1.25
)


@app.middleware("http")
async def limitar_tamanho_request(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Rejeita (413) requisições cujo Content-Length exceda o teto de upload."""
    tamanho = request.headers.get("content-length")
    if tamanho is not None and tamanho.isdigit() and int(tamanho) > _MAX_CORPO_BYTES:
        return JSONResponse(
            status_code=413,
            content={"detail": "Arquivo(s) acima do limite permitido."},
        )
    return await call_next(request)


@app.middleware("http")
async def cabecalhos_seguranca(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Adiciona cabeçalhos de segurança básicos a toda resposta.

    `X-Frame-Options: SAMEORIGIN` (não DENY) porque a ficha exibe o currículo
    original num `<iframe>` same-origin — DENY quebraria o visualizador.
    """
    resposta = await call_next(request)
    resposta.headers.setdefault("X-Content-Type-Options", "nosniff")
    resposta.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    resposta.headers.setdefault("Referrer-Policy", "no-referrer")
    return resposta


# --- API ---
app.include_router(health.router, prefix="/api")
app.include_router(vagas.router, prefix="/api")
app.include_router(lotes.router, prefix="/api")
app.include_router(avaliacoes.router, prefix="/api")
app.include_router(notificacoes.router, prefix="/api")
app.include_router(metricas.router, prefix="/api")
app.include_router(configuracao.router, prefix="/api")


# --- Frontend (SPA) ---
_dist = configuracoes.frontend_dist
_index = _dist / "index.html"

if (_dist / "assets").is_dir():
    # Arquivos estáticos com hash do Vite (JS/CSS/fontes).
    app.mount("/assets", StaticFiles(directory=_dist / "assets"), name="assets")


@app.get("/{full_path:path}", include_in_schema=False)
def servir_spa(full_path: str) -> FileResponse:
    """Serve o frontend: arquivos reais quando existem, senão `index.html`.

    Qualquer rota não-`/api` que não corresponda a um arquivo do build cai no
    `index.html`, permitindo que o roteamento client-side do React assuma.
    """
    # Rotas de API desconhecidas devem retornar 404 (não o HTML do SPA).
    if full_path.startswith("api/") or full_path == "api":
        raise HTTPException(status_code=404, detail="Rota de API não encontrada")

    if not _index.is_file():
        raise HTTPException(
            status_code=503,
            detail=(
                "Frontend ainda não foi buildado. Rode `make build` "
                "(ou `cd frontend && npm install && npm run build`)."
            ),
        )

    candidato = (_dist / full_path).resolve()
    # Impede *path traversal* para fora do diretório do build.
    if (
        full_path
        and _dist.resolve() in candidato.parents
        and candidato.is_file()
    ):
        return FileResponse(candidato)

    return FileResponse(_index)
