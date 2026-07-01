import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AlertTriangle, RotateCcw, Star } from 'lucide-react'

import { reprocessarFalhas } from '../api'
import { nomeExibicao, pct, recoBadge, ZONA_INFO } from '../labels'
import type { RankingVaga, ZonaDecisao } from '../types'

type Filtro = 'todos' | ZonaDecisao

const ORDEM_CHIPS: { valor: Filtro; rotulo: string; classe: string }[] = [
  { valor: 'todos', rotulo: 'Todos', classe: 'todos' },
  { valor: 'entra', rotulo: ZONA_INFO.entra.label, classe: 'entra' },
  { valor: 'avaliar', rotulo: ZONA_INFO.avaliar.label, classe: 'avaliar' },
  { valor: 'cai', rotulo: ZONA_INFO.cai.label, classe: 'cai' },
]

/**
 * Lista única de candidatos avaliados de uma vaga (cards coloridos por zona +
 * filtro + faixa de falhas). Reutilizado na tela de resultado do lote e na aba
 * "Candidatos" da vaga.
 */
export default function RankingCandidatos({ ranking }: { ranking: RankingVaga }) {
  const navigate = useNavigate()
  const [filtro, setFiltro] = useState<Filtro>('todos')
  const [reprocessando, setReprocessando] = useState(false)

  const linhasFiltradas = useMemo(() => {
    if (filtro === 'todos') return ranking.linhas
    return ranking.linhas.filter((l) => l.zona === filtro)
  }, [ranking, filtro])

  async function aoReprocessar() {
    setReprocessando(true)
    try {
      const r = await reprocessarFalhas(ranking.vaga_id)
      if (r.lote_id) navigate(`/triagem/${r.lote_id}`)
      else setReprocessando(false)
    } catch {
      setReprocessando(false)
    }
  }

  // Aviso compacto e recuperável (não a faixa grande de antes): some quando não
  // há falhas. As falhas viram raras com o retry automático no backend.
  const avisoFalhas = ranking.falhas.length > 0 && (
    <div className="falhas-aviso">
      <span>
        <AlertTriangle size={15} /> {ranking.falhas.length} currículo(s) não processados (instabilidade
        momentânea da IA).
      </span>
      <button className="btn btn-secondary btn-sm" type="button" disabled={reprocessando} onClick={aoReprocessar}>
        <RotateCcw size={14} /> {reprocessando ? 'Reprocessando…' : 'Reprocessar'}
      </button>
    </div>
  )

  if (ranking.total_avaliados === 0) {
    return (
      <>
        {avisoFalhas}
        {ranking.falhas.length === 0 && (
          <div className="card elevation-2">
            <div className="card-body">
              <p className="dica">
                Nenhum candidato avaliado ainda nesta vaga. Envie currículos para começar.
              </p>
            </div>
          </div>
        )}
      </>
    )
  }

  return (
    <>
      {avisoFalhas}
      {ranking.total_avaliados > 0 && (
        <div className="hero-taxa elevation-3">
          <div className="hero-taxa-num">{pct(ranking.taxa_auto_decisao)}</div>
          <div className="hero-taxa-texto">
            <strong>Taxa de auto-decisão</strong>
            <span>
              A IA resolveu sozinha {pct(ranking.taxa_auto_decisao)} dos {ranking.total_avaliados}{' '}
              candidatos avaliados nesta vaga. O restante vai para você revisar.
            </span>
          </div>
        </div>
      )}

      {ranking.total_avaliados > 0 && (
        <>
          <div className="filtro-chips">
            {ORDEM_CHIPS.map((chip) => {
              const qtd =
                chip.valor === 'todos'
                  ? ranking.total_avaliados
                  : (ranking.contagens?.[chip.valor] ?? 0)
              return (
                <button
                  key={chip.valor}
                  type="button"
                  className={`chip-filtro chip-${chip.classe} ${filtro === chip.valor ? 'ativo' : ''}`}
                  onClick={() => setFiltro(chip.valor)}
                >
                  {chip.rotulo}
                  <span className="chip-contagem">{qtd}</span>
                </button>
              )
            })}
          </div>

          <div className="cand-lista">
            {linhasFiltradas.map((linha) => {
              const badge = recoBadge(linha.recomendacao)
              const zona = linha.zona ?? 'avaliar'
              return (
                <button
                  key={linha.candidato_id}
                  type="button"
                  className="cand-card elevation-2"
                  onClick={() => navigate(`/candidatos/${linha.candidato_id}`)}
                >
                  <div className={`cand-circ cand-circ-${zona}`}>
                    <span className="cand-circ-num">{linha.score_final.toFixed(0)}</span>
                    <span className="cand-circ-lbl">score</span>
                  </div>
                  <div className="cand-main">
                    <div className="cand-topo">
                      <span className="cand-id">{nomeExibicao(linha)}</span>
                    </div>
                    <div className="cand-sinais">
                      {linha.sinais_fortes.length === 0 &&
                        linha.n_flags === 0 &&
                        linha.ressalvas.length === 0 && (
                          <span className="cand-sinal cand-sinal-vazio">Sem destaques fortes</span>
                        )}
                      {linha.sinais_fortes.map((s) => (
                        <span key={s} className="cand-sinal">
                          <Star size={12} /> {s}
                        </span>
                      ))}
                      {linha.ressalvas.length > 0 && (
                        <span className="cand-sinal cand-sinal-ressalva">
                          <AlertTriangle size={12} /> {linha.ressalvas.length}{' '}
                          {linha.ressalvas.length === 1
                            ? 'informação a confirmar'
                            : 'informações a confirmar'}
                        </span>
                      )}
                      {linha.n_flags > 0 && (
                        <span className="cand-sinal cand-sinal-flag">
                          <AlertTriangle size={12} /> {linha.n_flags} ponto(s) de atenção
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="cand-direita">
                    <span className={`badge ${badge.classe}`}>{badge.label}</span>
                  </div>
                </button>
              )
            })}
            {linhasFiltradas.length === 0 && (
              <p className="dica">Nenhum candidato neste filtro.</p>
            )}
          </div>
        </>
      )}
    </>
  )
}
