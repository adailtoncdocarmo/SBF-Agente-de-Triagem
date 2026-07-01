"""Ingestão de currículos — extrai texto de PDF/TXT/DOCX.

Estratégia: PDF com texto selecionável via `pypdf` (rápido); se vier quase vazio
(layout em colunas, tabelas), cai para `pdfplumber`. DOCX via `python-docx`.
PDFs escaneados (imagem) precisariam de OCR (Claude Vision) — fora do MVP: o
upload detecta texto vazio e avisa o usuário (não lê em silêncio).
"""

from __future__ import annotations

import io
import logging

logger = logging.getLogger("triagem.ingest")

_MINIMO_TEXTO = 30  # abaixo disso, tenta o fallback


def _via_pypdf(conteudo: bytes) -> str:
    from pypdf import PdfReader

    leitor = PdfReader(io.BytesIO(conteudo))
    return "\n".join((pagina.extract_text() or "") for pagina in leitor.pages)


def _via_pdfplumber(conteudo: bytes) -> str:
    import pdfplumber

    with pdfplumber.open(io.BytesIO(conteudo)) as pdf:
        return "\n".join((p.extract_text() or "") for p in pdf.pages)


def _via_docx(conteudo: bytes) -> str:
    from docx import Document

    doc = Document(io.BytesIO(conteudo))
    return "\n".join(p.text for p in doc.paragraphs)


def extrair_texto(nome_arquivo: str, conteudo: bytes) -> str:
    """Extrai o texto de um currículo (PDF, TXT ou DOCX).

    Retorna string vazia quando não há texto extraível (ex.: PDF escaneado/imagem)
    — o chamador (upload) trata isso avisando o usuário, em vez de ler em silêncio.
    """
    nome = nome_arquivo.lower()
    if nome.endswith(".txt"):
        return conteudo.decode("utf-8", errors="ignore")

    if nome.endswith(".pdf"):
        try:
            texto = _via_pypdf(conteudo)
        except Exception:
            logger.warning("pypdf falhou em %s; tentando pdfplumber.", nome_arquivo)
            texto = ""
        if len(texto.strip()) < _MINIMO_TEXTO:
            try:
                texto = _via_pdfplumber(conteudo)
            except Exception:
                logger.exception("pdfplumber também falhou em %s.", nome_arquivo)
        return texto

    if nome.endswith(".docx"):
        try:
            return _via_docx(conteudo)
        except Exception:
            logger.exception("Falha ao ler DOCX %s.", nome_arquivo)
            return ""

    # Outros formatos: tenta decodificar como texto.
    return conteudo.decode("utf-8", errors="ignore")
