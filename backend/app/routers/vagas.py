"""Endpoints de Vagas — cadastro, régua automática, ranking acumulado e reprocesso.

Fluxo: o usuário cola a descrição → o Agente Régua propõe a régua → o usuário
edita e salva. A régua é **sempre editável**: ao salvar uma nova com candidatos
já avaliados, a vaga é reprocessada (determinístico se só mudaram pesos/cortes;
reextração com IA se mudaram rótulos/knockouts).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models_db import Vaga
from app.routers._servico import (
    carregar_avaliacoes_da_vaga,
    carregar_falhas_da_vaga,
    contar_avaliados_da_vaga,
)
from app.schemas.regua import Regua
from app.schemas.saidas import RankingVaga
from app.triagem.agente_regua import propor_regua
from app.triagem.cliente_llm import ClienteLLM
from app.triagem.ficha import montar_ranking_vaga
from app.triagem.fila import fila
from app.triagem.orquestrador import _registrador_custo, gerar_sinteses_vaga
from app.triagem.reprocesso import (
    precisa_reextrair,
    reenfileirar_falhas_da_vaga,
    reprocessar_vaga_deterministico,
    resetar_vaga_para_reextracao,
)

router = APIRouter(tags=["vagas"])


class NovaVaga(BaseModel):
    titulo: str
    descricao: str


class ReprocessoInfo(BaseModel):
    """Resultado do reprocesso ao salvar a régua (alimenta o modal do front)."""

    modo: str | None = None  # "deterministico" | "ia" | None (sem candidatos)
    afetados: int = 0
    reprocessado: bool = False


class VagaResposta(BaseModel):
    id: int
    titulo: str
    descricao: str
    congelada: bool
    status: str = "ativa"  # "ativa" | "arquivada"
    total_avaliados: int = 0
    regua: Regua
    reprocesso: ReprocessoInfo | None = None


class VagaResumo(BaseModel):
    id: int
    titulo: str
    congelada: bool
    status: str = "ativa"  # "ativa" | "arquivada"
    total_avaliados: int = 0


@router.post("/vagas", response_model=VagaResposta, status_code=201)
async def criar_vaga(dados: NovaVaga, db: Session = Depends(get_db)) -> VagaResposta:
    """Cria a vaga e dispara o Agente Régua → retorna a régua proposta."""
    cliente = ClienteLLM(ao_registrar_custo=_registrador_custo)
    if not cliente.disponivel:
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY ausente — configure o .env para gerar a régua.",
        )
    regua = await propor_regua(cliente, dados.descricao)
    vaga = Vaga(
        titulo=dados.titulo,
        descricao=dados.descricao,
        regua_json=regua.model_dump(mode="json"),
        congelada=False,
    )
    db.add(vaga)
    db.commit()
    db.refresh(vaga)
    return VagaResposta(
        id=vaga.id,
        titulo=vaga.titulo,
        descricao=vaga.descricao,
        congelada=False,
        status=vaga.status,
        total_avaliados=0,
        regua=regua,
    )


@router.put("/vagas/{vaga_id}", response_model=VagaResposta)
async def salvar_regua(
    vaga_id: int,
    regua: Regua,
    reprocessar: bool = True,
    db: Session = Depends(get_db),
) -> VagaResposta:
    """Salva a régua editada e, se já houver candidatos, reprocessa a vaga.

    - só pesos/cortes/pisos/volatilidades mudaram → recálculo determinístico (sem IA);
    - rótulos de critério ou knockouts mudaram → reextração com IA (re-enfileira).
    """
    vaga = db.get(Vaga, vaga_id)
    if vaga is None:
        raise HTTPException(status_code=404, detail="Vaga não encontrada.")

    regua_antiga = Regua.model_validate(vaga.regua_json)
    afetados = contar_avaliados_da_vaga(db, vaga_id)

    regua.congelada = True
    vaga.regua_json = regua.model_dump(mode="json")
    vaga.congelada = True
    db.commit()

    info = ReprocessoInfo(modo=None, afetados=afetados, reprocessado=False)
    if afetados > 0:
        modo = "ia" if precisa_reextrair(regua_antiga, regua) else "deterministico"
        info.modo = modo
        if reprocessar:
            if modo == "ia":
                if not ClienteLLM(ao_registrar_custo=_registrador_custo).disponivel:
                    raise HTTPException(
                        status_code=503,
                        detail="Mudança exige reextração com IA — configure a chave da API.",
                    )
                for lote_id in resetar_vaga_para_reextracao(vaga_id):
                    await fila.enfileirar(lote_id)
                info.reprocessado = True
            else:
                info.afetados = reprocessar_vaga_deterministico(vaga_id, regua)
                info.reprocessado = True
                # Preenche as sínteses (aderência/recomendação) que ainda faltam —
                # ex.: candidatos avaliados antes de a síntese existir/funcionar.
                cliente_sintese = ClienteLLM(ao_registrar_custo=_registrador_custo)
                if cliente_sintese.disponivel:
                    await gerar_sinteses_vaga(vaga_id, cliente_sintese)

    total = contar_avaliados_da_vaga(db, vaga_id)
    return VagaResposta(
        id=vaga.id,
        titulo=vaga.titulo,
        descricao=vaga.descricao,
        congelada=True,
        status=vaga.status,
        total_avaliados=total,
        regua=regua,
        reprocesso=info,
    )


@router.get("/vagas", response_model=list[VagaResumo])
def listar_vagas(
    status: str | None = None, db: Session = Depends(get_db)
) -> list[VagaResumo]:
    """Lista as vagas cadastradas (com a contagem de candidatos avaliados).

    `status` opcional ('ativa' | 'arquivada') filtra no servidor; sem ele,
    devolve todas (o front filtra/contabiliza por status).
    """
    consulta = select(Vaga).order_by(Vaga.criado_em.desc())
    if status is not None:
        consulta = consulta.where(Vaga.status == status)
    vagas = db.scalars(consulta)
    return [
        VagaResumo(
            id=v.id,
            titulo=v.titulo,
            congelada=v.congelada,
            status=v.status,
            total_avaliados=contar_avaliados_da_vaga(db, v.id),
        )
        for v in vagas
    ]


@router.get("/vagas/{vaga_id}", response_model=VagaResposta)
def obter_vaga(vaga_id: int, db: Session = Depends(get_db)) -> VagaResposta:
    """Detalha uma vaga, sua régua e a contagem acumulada de avaliados."""
    vaga = db.get(Vaga, vaga_id)
    if vaga is None:
        raise HTTPException(status_code=404, detail="Vaga não encontrada.")
    return VagaResposta(
        id=vaga.id,
        titulo=vaga.titulo,
        descricao=vaga.descricao,
        congelada=vaga.congelada,
        status=vaga.status,
        total_avaliados=contar_avaliados_da_vaga(db, vaga_id),
        regua=Regua.model_validate(vaga.regua_json),
    )


@router.post("/vagas/{vaga_id}/arquivar", response_model=VagaResumo)
def arquivar_vaga(vaga_id: int, db: Session = Depends(get_db)) -> VagaResumo:
    """Arquiva a vaga (sai da lista de ativas; nada é apagado)."""
    return _mudar_status_vaga(vaga_id, "arquivada", db)


@router.post("/vagas/{vaga_id}/restaurar", response_model=VagaResumo)
def restaurar_vaga(vaga_id: int, db: Session = Depends(get_db)) -> VagaResumo:
    """Restaura uma vaga arquivada de volta para ativa."""
    return _mudar_status_vaga(vaga_id, "ativa", db)


def _mudar_status_vaga(vaga_id: int, status: str, db: Session) -> VagaResumo:
    """Helper: muda o status da vaga (ativa/arquivada) e devolve o resumo."""
    vaga = db.get(Vaga, vaga_id)
    if vaga is None:
        raise HTTPException(status_code=404, detail="Vaga não encontrada.")
    vaga.status = status
    db.commit()
    return VagaResumo(
        id=vaga.id,
        titulo=vaga.titulo,
        congelada=vaga.congelada,
        status=vaga.status,
        total_avaliados=contar_avaliados_da_vaga(db, vaga_id),
    )


class ReprocessoFalhas(BaseModel):
    reenfileirados: int
    lote_id: int | None = None


@router.post("/vagas/{vaga_id}/reprocessar-falhas", response_model=ReprocessoFalhas)
async def reprocessar_falhas(
    vaga_id: int, db: Session = Depends(get_db)
) -> ReprocessoFalhas:
    """Recoloca na fila só os currículos que falharam (recuperação)."""
    vaga = db.get(Vaga, vaga_id)
    if vaga is None:
        raise HTTPException(status_code=404, detail="Vaga não encontrada.")
    if not ClienteLLM(ao_registrar_custo=_registrador_custo).disponivel:
        raise HTTPException(
            status_code=503,
            detail="Configure a chave da API da Anthropic em Configurações para reprocessar.",
        )
    qtd, lote_ids = reenfileirar_falhas_da_vaga(vaga_id)
    for lote_id in lote_ids:
        await fila.enfileirar(lote_id)
    return ReprocessoFalhas(reenfileirados=qtd, lote_id=lote_ids[0] if lote_ids else None)


@router.get("/vagas/{vaga_id}/ranking", response_model=RankingVaga)
def ranking_vaga(vaga_id: int, db: Session = Depends(get_db)) -> RankingVaga:
    """Ranking acumulado da vaga: lista única ordenada + contagens + falhas."""
    vaga = db.get(Vaga, vaga_id)
    if vaga is None:
        raise HTTPException(status_code=404, detail="Vaga não encontrada.")
    itens = carregar_avaliacoes_da_vaga(db, vaga_id)
    falhas = carregar_falhas_da_vaga(db, vaga_id)
    return montar_ranking_vaga(vaga_id, vaga.titulo, itens, falhas)
