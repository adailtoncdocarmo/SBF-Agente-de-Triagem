"""Estágio 9 — Ranking e ficha explicável (Python).

Monta o ranking acumulado da vaga (lista única ordenada por score, com os
critérios de desempate da Parte 6.6 como chaves secundárias, mais as contagens
por zona) e a ficha rastreável de cada candidato. A justificativa é gerada por
template e **sempre bate com os números** — nunca é texto livre da IA.
"""

from __future__ import annotations

from app.schemas.avaliacao import Avaliacao
from app.schemas.enums import Confianca, Severidade, StatusCritico, ZonaDecisao
from app.schemas.saidas import (
    ContagensZona,
    FalhaCandidato,
    FichaCandidato,
    LinhaRanking,
    RankingVaga,
)
from app.texto import limpar_dashes
from app.triagem.zonas import calcular_taxa_auto_decisao


def _limpar_avaliacao(av: Avaliacao) -> None:
    """Limpa, in-place, os travessões dos textos livres (IA) exibidos na ficha.

    Mexe só no objeto em memória da requisição — nada é regravado no banco.
    """
    av.ressalvas = [limpar_dashes(r) for r in av.ressalvas]
    for c in av.criterios:
        c.justificativa_nota = limpar_dashes(c.justificativa_nota)
        c.evidencias = [limpar_dashes(e) for e in c.evidencias]
        c.lacunas = [limpar_dashes(lac) for lac in c.lacunas]
    for f in av.flags.risco:
        f.descricao = limpar_dashes(f.descricao)

_ORDEM_CONFIANCA = {Confianca.ALTA: 3, Confianca.MEDIA: 2, Confianca.BAIXA: 1}

def sinais_fortes(av: Avaliacao, limite: int = 3) -> list[str]:
    """Rótulos dos critérios mais fortes do candidato (nota ≥ 3), p/ os cards."""
    fortes = sorted(
        (c for c in av.criterios if c.nota_0_4 >= 3),
        key=lambda c: (-c.nota_0_4, -c.peso),
    )
    return [c.rotulo for c in fortes[:limite]]


def _nota(av: Avaliacao, criterio_id: str) -> int:
    for c in av.criterios:
        if c.criterio == criterio_id:
            return c.nota_0_4
    return 0


def _soma_criticos(av: Avaliacao) -> int:
    return sum(c.nota_0_4 for c in av.criterios if c.critico)


def _flags_media_alta(av: Avaliacao) -> int:
    return sum(
        1
        for f in av.flags.risco
        if f.severidade in (Severidade.MEDIA, Severidade.ALTA, Severidade.CRITICA)
    )


def chave_ordenacao(av: Avaliacao) -> tuple:
    """Chave de ordenação decrescente (Framework 6.6): score → críticos →
    resultados → experiência → menos flags → confiança."""
    return (
        -av.score_final,
        -_soma_criticos(av),
        -_nota(av, "resultados"),
        -_nota(av, "experiencia"),
        _flags_media_alta(av),
        -_ORDEM_CONFIANCA.get(av.confianca, 0),
    )


def _pontos_fortes(av: Avaliacao) -> list[str]:
    """Rótulos onde o candidato foi bem (nota ≥ 3), do maior peso ao menor."""
    fortes = sorted(
        (c for c in av.criterios if c.nota_0_4 >= 3), key=lambda c: -c.peso
    )
    return [c.rotulo for c in fortes]


def _pontos_fracos(av: Avaliacao) -> list[str]:
    """Rótulos que mais puxaram a nota para baixo (nota ≤ 1, maior peso primeiro)."""
    fracos = sorted(
        (c for c in av.criterios if c.nota_0_4 <= 1), key=lambda c: -c.peso
    )
    return [c.rotulo for c in fracos]


def montar_justificativa(av: Avaliacao, posicao: int, total: int) -> str:
    """Justificativa enxuta e honesta: por que o candidato tirou essa nota."""
    fortes = _pontos_fortes(av)
    fracos = _pontos_fracos(av)
    partes = [f"Aderência (posição {posicao} de {total})."]
    if fracos:
        partes.append("Nota limitada por " + ", ".join(fracos[:3]) + ".")
    if fortes:
        partes.append("Destaque em " + ", ".join(fortes[:3]) + ".")
    if not fortes and not fracos:
        partes.append("Desempenho intermediário nos critérios da vaga.")
    if av.motivo_zona:
        partes.append(av.motivo_zona)
    return " ".join(partes)


def montar_orientacao(av: Avaliacao) -> str:
    """Texto curto que ORIENTA o RH sobre o candidato (a partir da decisão)."""
    fortes = _pontos_fortes(av)
    fortes_txt = ", ".join(fortes[:2]) if fortes else ""
    ressalva = av.ressalvas[0] if av.ressalvas else ""

    if av.zona_decisao == ZonaDecisao.ENTRA:
        txt = "Bom encaixe — avançar para entrevista."
        if fortes_txt:
            txt += f" Destaques: {fortes_txt}."
        if ressalva:
            txt += f" {ressalva}."
        return txt

    if av.zona_decisao == ZonaDecisao.CAI:
        fracos = _pontos_fracos(av)
        motivo = fracos[0] if fracos else "aderência abaixo do corte da vaga"
        return (
            f"Abaixo do perfil — não recomendado avançar. Principal limitação: {motivo}."
        )

    # AVALIAR (amarelo) — revisão humana.
    txt = "Caso de revisão humana."
    if fortes_txt:
        txt += f" Tem força em {fortes_txt}, mas é preciso validar antes de decidir."
    else:
        txt += " Vale uma conversa para confirmar os pontos em aberto."
    if ressalva:
        txt += f" {ressalva}."
    return txt


def montar_ficha(
    candidato_id: int,
    nome_arquivo: str,
    avaliacao: Avaliacao,
    posicao: int | None = None,
    total_lote: int | None = None,
    nome_candidato: str | None = None,
) -> FichaCandidato:
    """Monta a ficha completa de um candidato a partir da sua avaliação."""
    # Limpa os travessões dos textos livres da IA antes de derivar os campos.
    _limpar_avaliacao(avaliacao)
    destaques = [ev for c in avaliacao.criterios if c.nota_0_4 >= 3 for ev in c.evidencias]
    lacunas = [lac for c in avaliacao.criterios if c.nota_0_4 <= 2 for lac in c.lacunas]
    # Requisitos knockout não evidenciados também são lacunas a validar.
    for k in avaliacao.portao_1:
        if k.estado.value == "nao_evidenciado":
            lacunas.append(f"Requisito '{limpar_dashes(k.requisito)}' não evidenciado no CV.")

    # Prefere os textos enriquecidos pela IA (estágio "sintese"); se vazios
    # (IA indisponível ou ainda não rodou), cai no texto de template.
    justificativa = limpar_dashes(
        avaliacao.sintese_aderencia
        or (
            montar_justificativa(avaliacao, posicao, total_lote)
            if posicao is not None and total_lote is not None
            else avaliacao.motivo_zona
        )
    )
    orientacao = limpar_dashes(avaliacao.sintese_recomendacao or montar_orientacao(avaliacao))

    return FichaCandidato(
        candidato_id=candidato_id,
        id_anonimo=avaliacao.candidato,
        nome_candidato=nome_candidato,
        nome_arquivo=nome_arquivo,
        vaga=avaliacao.vaga,
        posicao=posicao,
        total_lote=total_lote,
        score_final=avaliacao.score_final,
        percentil=avaliacao.calibracao_lote.percentil if avaliacao.calibracao_lote else None,
        recomendacao=avaliacao.recomendacao,
        confianca=avaliacao.confianca,
        zona=avaliacao.zona_decisao,
        orientacao=orientacao,
        justificativa=justificativa,
        destaques=destaques[:6],
        lacunas=lacunas[:6],
        avaliacao=avaliacao,
    )


def _montar_linha(
    cid: int,
    nome: str,
    av: Avaliacao,
    posicao: int,
    nome_candidato: str | None = None,
) -> LinhaRanking:
    """Monta uma linha do ranking (com zona e sinais para a lista colorida)."""
    return LinhaRanking(
        candidato_id=cid,
        id_anonimo=av.candidato,
        nome_arquivo=nome,
        nome_candidato=nome_candidato,
        posicao=posicao,
        score_final=av.score_final,
        percentil=av.calibracao_lote.percentil if av.calibracao_lote else None,
        recomendacao=av.recomendacao,
        confianca=av.confianca,
        zona=av.zona_decisao,
        sinais_fortes=[limpar_dashes(s) for s in sinais_fortes(av)],
        n_flags=_flags_media_alta(av),
        ressalvas=[limpar_dashes(r) for r in av.ressalvas],
    )


def montar_ranking_vaga(
    vaga_id: int,
    vaga: str,
    itens: list[tuple[int, str, str | None, Avaliacao]],
    falhas: list[FalhaCandidato] | None = None,
) -> RankingVaga:
    """Ranking acumulado de TODA a vaga: lista única ordenada + contagens por zona.

    Args:
        itens: lista de `(candidato_id, nome_arquivo, nome_candidato, Avaliacao)`.
    """
    ordenados = sorted(itens, key=lambda it: chave_ordenacao(it[3]))
    taxa = calcular_taxa_auto_decisao(
        [av.zona_decisao for *_, av in ordenados if av.zona_decisao]
    )
    contagens = ContagensZona()
    linhas: list[LinhaRanking] = []
    for posicao, (cid, nome, nome_cand, av) in enumerate(ordenados, start=1):
        linhas.append(_montar_linha(cid, nome, av, posicao, nome_cand))
        if av.zona_decisao == ZonaDecisao.ENTRA:
            contagens.entra += 1
        elif av.zona_decisao == ZonaDecisao.AVALIAR:
            contagens.avaliar += 1
        elif av.zona_decisao == ZonaDecisao.CAI:
            contagens.cai += 1

    return RankingVaga(
        vaga_id=vaga_id,
        vaga=vaga,
        total_avaliados=len(ordenados),
        taxa_auto_decisao=taxa,
        contagens=contagens,
        linhas=linhas,
        falhas=falhas or [],
    )
