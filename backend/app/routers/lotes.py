"""Endpoints de Lotes — upload de currículos e status do processamento.

O cegamento (Stage 0) roda **aqui, no upload**: a IA só recebe o `texto_cegado`
(sem PII). O **arquivo original** é guardado à parte (`arquivo_original`) para o
RH autorizado visualizar o CV na ficha — ele nunca é enviado à IA. O lote vai
para a fila assíncrona; o usuário pode sair da tela.

O ranking é servido por vaga (`/vagas/{id}/ranking`), que acumula todos os lotes.
"""

from __future__ import annotations

import hashlib

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import configuracoes
from app.database import get_db
from app.models_db import Candidato, Lote, Notificacao, Vaga
from app.schemas.enums import StatusCandidato, StatusLote
from app.triagem.cegamento import cegar_cv
from app.triagem.cliente_llm import ClienteLLM
from app.triagem.fila import fila
from app.triagem.ingest import extrair_texto
from app.triagem.orquestrador import _registrador_custo

router = APIRouter(tags=["lotes"])

# Extensões de currículo suportadas por `extrair_texto`.
_EXTENSOES_PERMITIDAS = (".pdf", ".txt", ".docx")

_MIME_POR_EXT = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


class LoteCriado(BaseModel):
    lote_id: int
    total: int


class StatusLoteResposta(BaseModel):
    lote_id: int
    vaga_id: int
    status: str
    total: int
    concluidos: int
    taxa_auto_decisao: float | None = None


@router.post("/vagas/{vaga_id}/lotes", response_model=LoteCriado, status_code=202)
async def criar_lote(
    vaga_id: int,
    arquivos: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
) -> LoteCriado:
    """Recebe N currículos, cega cada um, cria o lote e enfileira."""
    vaga = db.get(Vaga, vaga_id)
    if vaga is None:
        raise HTTPException(status_code=404, detail="Vaga não encontrada.")
    # Pré-checagem amigável: sem chave de IA, todo CV falharia silenciosamente.
    if not ClienteLLM(ao_registrar_custo=_registrador_custo).disponivel:
        raise HTTPException(
            status_code=503,
            detail="Configure a chave da API da Anthropic em Configurações para triar.",
        )
    if not arquivos:
        raise HTTPException(status_code=400, detail="Envie ao menos um currículo.")
    if len(arquivos) > configuracoes.max_arquivos_por_lote:
        raise HTTPException(
            status_code=413,
            detail=f"Máximo de {configuracoes.max_arquivos_por_lote} currículos por lote.",
        )

    limite_bytes = configuracoes.max_tamanho_arquivo_mb * 1024 * 1024
    lote = Lote(vaga_id=vaga_id, status=StatusLote.ENFILEIRADO.value, total=0)
    db.add(lote)
    db.flush()  # garante lote.id

    vistos: set[str] = set()
    indice = 0
    # Arquivos não lidos (formato inválido, grande demais, ou sem texto extraível)
    # não abortam o lote: são pulados e o usuário é avisado por notificação.
    rejeitados: list[tuple[str, str]] = []
    for arquivo in arquivos:
        rotulo = arquivo.filename or "arquivo sem nome"
        nome = (arquivo.filename or "cv").lower()
        ext = next((e for e in _EXTENSOES_PERMITIDAS if nome.endswith(e)), None)
        if ext is None:
            rejeitados.append((rotulo, "formato não aceito (use PDF, TXT ou DOCX)"))
            continue
        conteudo = await arquivo.read()
        if len(conteudo) > limite_bytes:
            rejeitados.append((rotulo, f"excede {configuracoes.max_tamanho_arquivo_mb} MB"))
            continue
        texto_bruto = extrair_texto(arquivo.filename or "cv", conteudo)
        if not texto_bruto.strip():
            # PDF escaneado/imagem ou documento vazio: sem texto para a IA ler.
            rejeitados.append((rotulo, "sem texto legível (PDF escaneado/imagem?)"))
            continue
        hash_cv = hashlib.sha256(texto_bruto.encode("utf-8")).hexdigest()
        if hash_cv in vistos:  # dedupe dentro do lote
            continue
        vistos.add(hash_cv)
        indice += 1
        id_anonimo = f"CAND-{indice:04d}"
        resultado = cegar_cv(texto_bruto, id_anonimo)
        mime = arquivo.content_type or _MIME_POR_EXT.get(ext, "application/octet-stream")
        db.add(
            Candidato(
                lote_id=lote.id,
                nome_arquivo=arquivo.filename or f"cv-{indice}",
                nome_candidato=resultado.nome_detectado,
                hash_cv=hash_cv,
                id_anonimo=id_anonimo,
                texto_cegado=resultado.texto_cegado,
                # Original guardado só para visualização do RH (nunca vai à IA).
                arquivo_original=conteudo,
                arquivo_mime=mime,
                status=StatusCandidato.ENFILEIRADO.value,
                estagio_atual="cegamento",
            )
        )

    if indice == 0:
        db.rollback()
        motivos = "; ".join(f"{nome} ({motivo})" for nome, motivo in rejeitados)
        raise HTTPException(
            status_code=400,
            detail=(
                "Nenhum currículo legível foi extraído. O sistema aceita PDF, TXT ou DOCX "
                "com texto (PDFs escaneados/imagem não são lidos)."
                + (f" Arquivos ignorados: {motivos}." if motivos else "")
            ),
        )

    # Avisa o usuário sobre os arquivos que não puderam ser lidos (sino).
    if rejeitados:
        nomes = ", ".join(nome for nome, _ in rejeitados)
        db.add(
            Notificacao(
                lote_id=lote.id,
                payload_json={
                    "titulo": f"{len(rejeitados)} currículo(s) não foram lidos",
                    "mensagem": (
                        f"Não foi possível ler: {nomes}. "
                        "O sistema aceita PDF, TXT ou DOCX com texto — "
                        "PDFs escaneados/imagem não são lidos."
                    ),
                    "link": f"/triagem/{lote.id}",
                },
            )
        )

    lote.total = indice
    db.commit()
    await fila.enfileirar(lote.id)
    return LoteCriado(lote_id=lote.id, total=indice)


@router.get("/lotes/{lote_id}", response_model=StatusLoteResposta)
def status_lote(lote_id: int, db: Session = Depends(get_db)) -> StatusLoteResposta:
    """Status + progresso X/N de um lote (para o acompanhamento na tela)."""
    lote = db.get(Lote, lote_id)
    if lote is None:
        raise HTTPException(status_code=404, detail="Lote não encontrado.")
    concluidos = len(
        list(
            db.scalars(
                select(Candidato).where(
                    Candidato.lote_id == lote_id,
                    Candidato.status.in_(
                        [StatusCandidato.CONCLUIDO.value, StatusCandidato.ERRO.value]
                    ),
                )
            )
        )
    )
    return StatusLoteResposta(
        lote_id=lote.id,
        vaga_id=lote.vaga_id,
        status=lote.status,
        total=lote.total,
        concluidos=concluidos,
        taxa_auto_decisao=lote.taxa_auto_decisao,
    )
