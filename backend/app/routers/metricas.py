"""Endpoints de Métricas: tornam a IA mensurável (gargalo 03).

`GET /metricas` devolve métricas operacionais reais (throughput, zonas,
latência, custo, cache hit) a partir dos lotes e da telemetria de custo.
"""

from __future__ import annotations

import statistics

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import configuracao_runtime as cfg_rt
from app.config import configuracoes
from app.database import get_db
from app.models_db import Lote, RegistroCusto
from app.schemas.enums import StatusLote

router = APIRouter(tags=["metricas"])


class CustoEstagio(BaseModel):
    estagio: str
    chamadas: int
    custo_usd: float
    custo_brl: float
    latencia_media_ms: float


class MetricasOperacionais(BaseModel):
    lotes_concluidos: int
    cvs_avaliados: int
    taxa_auto_decisao_media: float
    # Alvo de throughput configurado (Framework 1.3): a régua de ouro exige
    # "ter o alvo E medi-lo". Devolvido junto para a UI comparar realizado×alvo.
    alvo_auto_decisao: float
    distribuicao_zonas: dict[str, int]
    custo_total_usd: float
    custo_total_brl: float
    custo_medio_por_cv_usd: float
    custo_medio_por_cv_brl: float
    # Câmbio usado na conversão (exibição) — o front formata "$X · R$Y".
    taxa_usd_brl: float
    chamadas_api: int
    latencia_media_ms: float
    latencia_p95_ms: float
    cache_hit_ratio: float
    custo_por_estagio: list[CustoEstagio]


# Ordem cronológica das etapas no pipeline (régua → portão → scoring → flags →
# comparação → síntese). A tabela de custo segue esta sequência para o RH ler o
# fluxo na ordem em que acontece, não em ordem alfabética da chave interna.
_ORDEM_ESTAGIOS: dict[str, int] = {
    "regua": 0,
    "portao1": 1,
    "scoring": 2,
    "flags": 3,
    "comparacao": 4,
    "sintese": 5,
}


def _ordem_estagio(estagio: str) -> tuple[int, str]:
    """Chave de ordenação cronológica; estágios desconhecidos vão para o fim."""
    return (_ORDEM_ESTAGIOS.get(estagio, len(_ORDEM_ESTAGIOS)), estagio)


def _p95(valores: list[float]) -> float:
    if not valores:
        return 0.0
    ordenados = sorted(valores)
    if len(ordenados) == 1:
        return ordenados[0]
    indice = max(0, int(round(0.95 * (len(ordenados) - 1))))
    return ordenados[indice]


@router.get("/metricas", response_model=MetricasOperacionais)
def metricas_operacionais(db: Session = Depends(get_db)) -> MetricasOperacionais:
    """Agrega métricas reais de execução (lotes + custos)."""
    lotes = list(
        db.scalars(select(Lote).where(Lote.status == StatusLote.CONCLUIDO.value))
    )
    cvs = sum(lote.concluidos for lote in lotes)
    n_entra = sum(lote.n_entra for lote in lotes)
    n_avaliar = sum(lote.n_avaliar for lote in lotes)
    n_cai = sum(lote.n_cai for lote in lotes)
    taxas = [lote.taxa_auto_decisao for lote in lotes if lote.taxa_auto_decisao is not None]
    taxa_media = round(statistics.mean(taxas), 4) if taxas else 0.0

    custos = list(db.scalars(select(RegistroCusto)))
    custo_total = round(sum(c.custo_usd for c in custos), 4)
    latencias = [float(c.latencia_ms) for c in custos]
    tokens_in = sum(c.tokens_in for c in custos)
    tokens_cache = sum(c.tokens_cache_read for c in custos)
    cache_ratio = (
        round(tokens_cache / (tokens_cache + tokens_in), 4)
        if (tokens_cache + tokens_in) > 0
        else 0.0
    )

    taxa_brl = configuracoes.taxa_usd_brl

    # Só os estágios de triagem real entram no quadro de custo. Os `dry_*`
    # (testes de skill da tela Configurações) são ensaios, não produção — poluem
    # a evidência de custo, então ficam de fora.
    por_estagio: dict[str, list[RegistroCusto]] = {}
    for c in custos:
        if c.estagio.startswith("dry_"):
            continue
        por_estagio.setdefault(c.estagio, []).append(c)
    custo_estagios = [
        CustoEstagio(
            estagio=estagio,
            chamadas=len(itens),
            custo_usd=round(sum(i.custo_usd for i in itens), 4),
            custo_brl=round(sum(i.custo_usd for i in itens) * taxa_brl, 4),
            latencia_media_ms=round(statistics.mean([i.latencia_ms for i in itens]), 1),
        )
        for estagio, itens in sorted(
            por_estagio.items(), key=lambda kv: _ordem_estagio(kv[0])
        )
    ]

    alvo = float(cfg_rt.obter_thresholds_default().get("alvo_auto_decisao", 0.0))
    custo_medio_cv = round(custo_total / cvs, 4) if cvs else 0.0

    return MetricasOperacionais(
        lotes_concluidos=len(lotes),
        cvs_avaliados=cvs,
        taxa_auto_decisao_media=taxa_media,
        alvo_auto_decisao=alvo,
        distribuicao_zonas={"entra": n_entra, "avaliar": n_avaliar, "cai": n_cai},
        custo_total_usd=custo_total,
        custo_total_brl=round(custo_total * taxa_brl, 4),
        custo_medio_por_cv_usd=custo_medio_cv,
        custo_medio_por_cv_brl=round(custo_medio_cv * taxa_brl, 4),
        taxa_usd_brl=taxa_brl,
        chamadas_api=len(custos),
        latencia_media_ms=round(statistics.mean(latencias), 1) if latencias else 0.0,
        latencia_p95_ms=round(_p95(latencias), 1),
        cache_hit_ratio=cache_ratio,
        custo_por_estagio=custo_estagios,
    )
