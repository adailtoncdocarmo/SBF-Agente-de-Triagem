import { useEffect, useState } from 'react'
import { Activity, DollarSign, Gauge, Timer } from 'lucide-react'

import PageHeader from '../components/PageHeader'
import { obterMetricas } from '../api'
import { itemPorPath } from '../nav'
import { brl, estagioDesc, estagioLabel, pct, ZONA_INFO } from '../labels'
import type { MetricasOperacionais } from '../types'

export default function Metricas() {
  const meta = itemPorPath('/')
  const [op, setOp] = useState<MetricasOperacionais | null>(null)

  useEffect(() => {
    obterMetricas().then(setOp).catch(() => {})
  }, [])

  // Câmbio do backend (com fallback): o R$ é calculado no front a partir do US$,
  // garantindo que a coluna apareça mesmo se o backend não mandar os campos *_brl.
  const taxa = op?.taxa_usd_brl ?? 5.4

  // Compara a taxa realizada com o alvo configurado (Framework 1.3: ter o alvo
  // E medi-lo). Só faz sentido quando há lote concluído.
  const atingiuAlvo = op ? op.taxa_auto_decisao_media >= op.alvo_auto_decisao : false

  type Kpi = {
    label: string
    valor: string
    icon: typeof Gauge
    dica?: string
    sub?: string
    ok?: boolean
  }
  const kpis: Kpi[] = [
    {
      label: 'Decisões automáticas',
      valor: op ? pct(op.taxa_auto_decisao_media) : '—',
      icon: Gauge,
      dica: 'Quanto a IA resolve sozinha, sem revisão humana.',
      sub: op ? `alvo ${pct(op.alvo_auto_decisao)}` : undefined,
      ok: op ? atingiuAlvo : undefined,
    },
    {
      label: 'Custo médio por currículo',
      valor: op ? `$${op.custo_medio_por_cv_usd.toFixed(3)}` : '—',
      icon: DollarSign,
      dica: op ? `≈ ${brl(op.custo_medio_por_cv_usd * taxa)} por CV` : 'Em dólar e em real.',
    },
    {
      label: 'Tempo de resposta (p95)',
      valor: op ? `${(op.latencia_p95_ms / 1000).toFixed(1)}s` : '—',
      icon: Timer,
      dica: '95% das avaliações terminam abaixo desse tempo.',
    },
    {
      label: 'Reaproveitamento de cache',
      valor: op ? pct(op.cache_hit_ratio) : '—',
      icon: Activity,
      dica: 'Parte dos textos reusada do cache. Quanto maior, menor o custo.',
    },
  ]

  // Totais da tabela de custo (somam só as etapas de triagem reais exibidas).
  const totalChamadas = op ? op.custo_por_estagio.reduce((s, e) => s + e.chamadas, 0) : 0
  const totalUsd = op ? op.custo_por_estagio.reduce((s, e) => s + e.custo_usd, 0) : 0

  return (
    <>
      <PageHeader titulo={meta.label} subtitulo={meta.subtitulo} />

      <div className="kpi-grid">
        {kpis.map(({ label, valor, icon: Icone, dica, sub, ok }) => (
          <div key={label} className={`kpi-card elevation-3${op ? '' : ' ghost'}`}>
            <div className="kpi-header">
              <span className="kpi-label">{label}</span>
              <div className="kpi-icon">
                <Icone size={16} strokeWidth={2} />
              </div>
            </div>
            <div className="kpi-value">{valor}</div>
            {dica && <div className="kpi-dica">{dica}</div>}
            {sub !== undefined && (
              <div className={`kpi-sub ${ok ? 'success' : 'danger'}`}>
                {ok ? '✓ no alvo' : '✗ abaixo'} · {sub}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Distribuição de zonas (operacional) */}
      {op && (
        <div className="card elevation-2 metricas-secao">
          <div className="card-header">
            <div className="card-title">Distribuição de zonas</div>
            <div className="card-subtitle">{op.cvs_avaliados} currículos em {op.lotes_concluidos} lote(s)</div>
          </div>
          <div className="card-body">
            <div className="zona-barras">
              <ZonaBarra rotulo={ZONA_INFO.entra.label} valor={op.distribuicao_zonas.entra} total={op.cvs_avaliados} classe="success" />
              <ZonaBarra rotulo={ZONA_INFO.avaliar.label} valor={op.distribuicao_zonas.avaliar} total={op.cvs_avaliados} classe="warning" />
              <ZonaBarra rotulo={ZONA_INFO.cai.label} valor={op.distribuicao_zonas.cai} total={op.cvs_avaliados} classe="danger" />
            </div>
          </div>
        </div>
      )}

      {/* Custo detalhado por etapa: evidência de onde o gasto de IA acontece */}
      {op && (
        <div className="card elevation-2 metricas-secao">
          <div className="card-header">
            <div className="card-title">Custo detalhado por etapa</div>
            <div className="card-subtitle">
              {totalChamadas} chamadas de IA · ${totalUsd.toFixed(4)} ·{' '}
              <strong>{brl(totalUsd * taxa)}</strong> no total
            </div>
          </div>
          <div className="card-body">
            <table className="tabela-criterios tabela-custo">
              <thead>
                <tr>
                  <th>Etapa</th>
                  <th>Chamadas</th>
                  <th>Custo (US$)</th>
                  <th>Custo (R$)</th>
                  <th>Tempo médio</th>
                </tr>
              </thead>
              <tbody>
                {op.custo_por_estagio.map((e) => (
                  <tr key={e.estagio}>
                    <td>
                      <div className="custo-etapa-nome">{estagioLabel(e.estagio)}</div>
                      {estagioDesc(e.estagio) && (
                        <div className="custo-etapa-desc">{estagioDesc(e.estagio)}</div>
                      )}
                    </td>
                    <td>{e.chamadas}</td>
                    <td className="score-cell">${e.custo_usd.toFixed(4)}</td>
                    <td className="score-cell">{brl(e.custo_usd * taxa, 4)}</td>
                    <td>{(e.latencia_media_ms / 1000).toFixed(1)}s</td>
                  </tr>
                ))}
                {op.custo_por_estagio.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="dica" style={{ textAlign: 'center' }}>
                      Nenhuma chamada de IA registrada ainda. Cadastre uma vaga e suba currículos.
                    </td>
                  </tr>
                ) : (
                  <tr className="custo-total">
                    <td><strong>Total</strong></td>
                    <td><strong>{totalChamadas}</strong></td>
                    <td className="score-cell"><strong>${totalUsd.toFixed(4)}</strong></td>
                    <td className="score-cell"><strong>{brl(totalUsd * taxa)}</strong></td>
                    <td></td>
                  </tr>
                )}
              </tbody>
            </table>
            <p className="custo-nota">
              As demais etapas (cegamento dos dados pessoais, conferência final, cálculo da nota,
              calibração e classificação por zona) rodam em <strong>Python</strong> e custam{' '}
              <strong>R$ 0</strong>. A IA só extrai sinais; o cálculo é determinístico.
            </p>
          </div>
        </div>
      )}
    </>
  )
}

function ZonaBarra({ rotulo, valor, total, classe }: { rotulo: string; valor: number; total: number; classe: string }) {
  const largura = total ? (valor / total) * 100 : 0
  return (
    <div className="zona-barra-linha">
      <span className="zona-barra-rotulo">{rotulo}</span>
      <div className="barra">
        <div className={`barra-preenchida ${classe}`} style={{ width: `${largura}%` }} />
      </div>
      <span className="zona-barra-valor">{valor}</span>
    </div>
  )
}
