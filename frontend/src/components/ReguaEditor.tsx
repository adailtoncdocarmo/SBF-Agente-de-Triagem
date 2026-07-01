import { useState } from 'react'
import { ChevronDown, Plus, SlidersHorizontal, Sparkles, Star, X } from 'lucide-react'

import {
  PRESETS_RIGOR,
  nivelDePeso,
  presetDeThresholds,
  type RigorPreset,
} from '../labels'
import type { Regua } from '../types'

const ORDEM_RIGOR: RigorPreset[] = ['flexivel', 'equilibrado', 'rigoroso']

interface ReguaEditorProps {
  regua: Regua
  onChange: (regua: Regua) => void
}

type Criterio = Regua['criterios'][number]

/**
 * Normaliza "importâncias" brutas em pesos inteiros que somam exatamente 100
 * (método do maior resto — espelha `agente_regua._renormalizar_pesos` no backend).
 * Assim o RH ajusta a importância relativa e nunca precisa "fechar em 100".
 */
function normalizarPesos(importancia: Record<string, number>): Record<string, number> {
  const ids = Object.keys(importancia)
  const valores = ids.map((id) => Math.max(0, Math.round(importancia[id])))
  const total = valores.reduce((a, b) => a + b, 0)
  const inteiros: number[] = []
  if (total === 0) {
    const base = Math.floor(100 / ids.length)
    ids.forEach(() => inteiros.push(base))
  } else {
    const exatos = valores.map((v) => (v / total) * 100)
    exatos.forEach((v) => inteiros.push(Math.floor(v)))
    let resto = 100 - inteiros.reduce((a, b) => a + b, 0)
    const ordem = ids
      .map((_, i) => i)
      .sort((a, b) => exatos[b] - inteiros[b] - (exatos[a] - inteiros[a]))
    for (let k = 0; resto > 0; k++, resto--) inteiros[ordem[k % ids.length]] += 1
  }
  // Garante soma exata 100 mesmo no caso total===0.
  let sobra = 100 - inteiros.reduce((a, b) => a + b, 0)
  for (let k = 0; sobra > 0; k++, sobra--) inteiros[k % ids.length] += 1
  return Object.fromEntries(ids.map((id, i) => [id, inteiros[i]]))
}

/**
 * Revisão guiada da régua: a IA propõe o que mais importa; o RH confere em
 * linguagem simples e confirma. Os controles finos (importância, decisivos,
 * nota mínima, tipo/nível) ficam num "Ajustar critérios" recolhido.
 */
export default function ReguaEditor({ regua, onChange }: ReguaEditorProps) {
  const [importancia, setImportancia] = useState<Record<string, number>>(() =>
    Object.fromEntries(regua.criterios.map((c) => [c.id, c.peso])),
  )
  const [avancado, setAvancado] = useState(false)
  const [novoReq, setNovoReq] = useState('')

  const nDecisivos = regua.criterios.filter((c) => c.e_critico).length
  const maxPeso = Math.max(...regua.criterios.map((c) => c.peso), 1)
  const ordenados = [...regua.criterios].sort((a, b) => b.peso - a.peso)

  function emitirPesos(novaImp: Record<string, number>) {
    const pesos = normalizarPesos(novaImp)
    onChange({
      ...regua,
      criterios: regua.criterios.map((c) => ({ ...c, peso: pesos[c.id] ?? c.peso })),
    })
  }
  function aoArrastar(id: string, v: number) {
    const next = { ...importancia, [id]: v }
    setImportancia(next)
    emitirPesos(next)
  }
  function patchCriterio(id: string, patch: Partial<Criterio>) {
    onChange({
      ...regua,
      criterios: regua.criterios.map((c) => (c.id === id ? { ...c, ...patch } : c)),
    })
  }
  function toggleDecisivo(id: string, atual: boolean) {
    if (!atual && nDecisivos >= 3) return // máx. 3 decisivos
    if (atual && nDecisivos <= 1) return // mín. 1 decisivo
    patchCriterio(id, { e_critico: !atual })
  }
  function removerReq(i: number) {
    onChange({ ...regua, knockouts: regua.knockouts.filter((_, idx) => idx !== i) })
  }
  function aplicarRigor(preset: RigorPreset) {
    const { corte_verde, corte_amarelo } = PRESETS_RIGOR[preset]
    onChange({
      ...regua,
      thresholds: { ...regua.thresholds, corte_verde, corte_amarelo },
    })
  }
  const rigorAtual = presetDeThresholds(regua.thresholds)
  function adicionarReq() {
    const r = novoReq.trim()
    if (!r) return
    onChange({
      ...regua,
      knockouts: [
        ...regua.knockouts,
        { requisito: r, objetivo: false, tipico_no_cv: true, justificativa_job_related: '' },
      ],
    })
    setNovoReq('')
  }
  function toggleObjetivo(i: number) {
    onChange({
      ...regua,
      knockouts: regua.knockouts.map((k, idx) => (idx === i ? { ...k, objetivo: !k.objetivo } : k)),
    })
  }
  function definirTipico(i: number, tipico: boolean) {
    onChange({
      ...regua,
      knockouts: regua.knockouts.map((k, idx) => (idx === i ? { ...k, tipico_no_cv: tipico } : k)),
    })
  }

  return (
    <div className="regua-guiada">
      {/* Cabeçalho de valor + detecção da IA */}
      <div className="regua-hero">
        <div className="regua-hero-icone">
          <Sparkles size={18} />
        </div>
        <div className="regua-hero-texto">
          <p className="regua-hero-titulo">A IA leu a vaga e definiu o que mais importa.</p>
          <p className="regua-hero-sub">
            Confira, ajuste se quiser e confirme: estes critérios viram a régua que avalia cada currículo.
          </p>
        </div>
      </div>

      {/* O que mais pesa nesta vaga */}
      <section className="card elevation-2">
        <div className="card-header">
          <div className="card-title">O que mais pesa nesta vaga</div>
        </div>
        <div className="card-body">
          <div className="peso-lista">
            {ordenados.map((c) => {
              const nivel = nivelDePeso(c.peso)
              return (
                <div key={c.id} className="peso-linha">
                  <div className="peso-rotulo">
                    <span>{c.rotulo}</span>
                    {c.e_critico && <Star size={13} className="decisivo-selo" fill="currentColor" />}
                  </div>
                  <div className="peso-barra">
                    <div className="peso-barra-preenchida" style={{ width: `${(c.peso / maxPeso) * 100}%` }} />
                  </div>
                  <span className={`peso-nivel ${nivel.classe}`}>{nivel.label}</span>
                </div>
              )
            })}
          </div>
          {nDecisivos > 0 && (
            <p className="decisivo-dica">
              <Star size={12} fill="currentColor" /> Critérios <strong>decisivos</strong>: quem não vai bem aqui
              não avança, mesmo com boa média geral.
            </p>
          )}
        </div>
      </section>

      {/* Requisitos da vaga */}
      <section className="card elevation-2">
        <div className="card-header">
          <div>
            <div className="card-title">Requisitos da vaga</div>
            <div className="card-subtitle">
              Liste só o que é <strong>indispensável</strong> para a vaga. Para cada requisito você
              decide o que acontece com quem não o cumpre:
            </div>
          </div>
        </div>
        <div className="card-body">
          {/* Legenda dos dois controles, com um exemplo claro e distinto para cada um. */}
          <div className="req-legenda">
            <div className="req-legenda-item">
              <span className="req-legenda-rotulo">Eliminatório</span>
              <span>
                descarta na hora quem <strong>declara que não atende</strong>. Use só para algo
                objetivo (ex.: <em>disponibilidade para fins de semana</em>).
              </span>
            </div>
            <div className="req-legenda-item">
              <span className="req-legenda-rotulo">Esperado no CV</span>
              <span>
                quando o currículo <strong>não menciona</strong> o requisito, a ausência conta
                contra. Use para algo que costuma aparecer (ex.: <em>uma formação exigida</em>).
              </span>
            </div>
            <div className="req-legenda-item">
              <span className="req-legenda-rotulo">Perguntar depois</span>
              <span>
                não penaliza quem não cita: vira lembrete para a entrevista. Use para o que
                raramente vem no CV (ex.: <em>CNH</em> ou <em>turno de trabalho</em>).
              </span>
            </div>
          </div>
          {regua.knockouts.length === 0 ? (
            <p className="dica">
              Nenhum requisito cadastrado. Adicione se houver algo indispensável (ex.: disponibilidade para
              fins de semana).
            </p>
          ) : (
            <div className="req-lista">
              {regua.knockouts.map((k, i) => (
                <div key={i} className="req-linha">
                  <span className="req-texto">{k.requisito}</span>
                  <label className="check req-toggle" title="Descarta quem declara não atender (requisito objetivo)">
                    <input type="checkbox" checked={k.objetivo} onChange={() => toggleObjetivo(i)} />
                    Eliminatório
                  </label>
                  {k.objetivo && (
                    <select
                      className="req-tipico"
                      value={k.tipico_no_cv ? 'sim' : 'nao'}
                      onChange={(e) => definirTipico(i, e.target.value === 'sim')}
                      title="O requisito costuma aparecer num currículo? 'Esperado no CV' penaliza a ausência; 'Perguntar depois' (ex.: CNH) não penaliza e vira lembrete da entrevista."
                    >
                      <option value="sim">Esperado no CV</option>
                      <option value="nao">Perguntar depois</option>
                    </select>
                  )}
                  <button type="button" className="req-chip-x" onClick={() => removerReq(i)} aria-label="Remover">
                    <X size={14} />
                  </button>
                </div>
              ))}
            </div>
          )}
          <div className="req-add">
            <input
              value={novoReq}
              onChange={(e) => setNovoReq(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault()
                  adicionarReq()
                }
              }}
              placeholder="Adicionar requisito (ex.: disponibilidade para fins de semana)"
            />
            <button type="button" className="btn btn-secondary btn-sm" onClick={adicionarReq}>
              <Plus size={14} /> Adicionar
            </button>
          </div>
        </div>
      </section>

      {/* Rigor da seleção (preset simples no lugar de percentil/piso crus) */}
      <section className="card elevation-2">
        <div className="card-header">
          <div>
            <div className="card-title">Rigor da seleção</div>
            <div className="card-subtitle">
              Quão exigente é o corte para um candidato entrar no verde (decisão automática).
            </div>
          </div>
        </div>
        <div className="card-body">
          <div className="rigor-seg">
            {ORDEM_RIGOR.map((p) => (
              <button
                key={p}
                type="button"
                className={`rigor-opcao ${rigorAtual === p ? 'ativo' : ''}`}
                onClick={() => aplicarRigor(p)}
              >
                {PRESETS_RIGOR[p].label}
              </button>
            ))}
          </div>
          <p className="dica" style={{ marginTop: 'var(--space-2)' }}>{PRESETS_RIGOR[rigorAtual].dica}</p>
        </div>
      </section>

      {/* Ajustar critérios (avançado, recolhido) */}
      <div className="ajuste-avancado">
        <button type="button" className="ajuste-toggle" onClick={() => setAvancado((v) => !v)}>
          <SlidersHorizontal size={15} /> Ajustar critérios
          <ChevronDown size={16} className={`ajuste-chevron ${avancado ? 'aberto' : ''}`} />
        </button>
        {avancado && (
          <div className="ajuste-corpo card elevation-1">
            <p className="dica">
              Arraste a importância de cada critério: o sistema equilibra o total sozinho. Marque de 1 a 3
              critérios <strong>decisivos</strong> (os essenciais da vaga); a <strong>nota mínima</strong> é o
              quanto o candidato precisa pontuar neles para não ser descartado.
            </p>
            <div className="ajuste-criterios">
              {regua.criterios.map((c) => {
                const trava = (!c.e_critico && nDecisivos >= 3) || (c.e_critico && nDecisivos <= 1)
                return (
                  <div key={c.id} className={`ajuste-linha elevation-1 ${c.e_critico ? 'decisivo' : ''}`}>
                    <div className="ajuste-linha-topo">
                      <span className="ajuste-rotulo">{c.rotulo}</span>
                      <div className="ajuste-peso-bloco">
                        <span className="ajuste-peso-num">{c.peso}</span>
                        <span className="ajuste-peso-cap">Peso</span>
                      </div>
                    </div>
                    <input
                      className="ajuste-range"
                      type="range"
                      min={0}
                      max={50}
                      value={importancia[c.id] ?? c.peso}
                      onChange={(e) => aoArrastar(c.id, Number(e.target.value))}
                    />
                    <div className="ajuste-controles">
                      <label className="check">
                        <input
                          type="checkbox"
                          checked={c.e_critico}
                          disabled={trava}
                          onChange={() => toggleDecisivo(c.id, c.e_critico)}
                        />
                        Decisivo
                      </label>
                      {c.e_critico && (
                        <label className="check">
                          Nota mínima
                          <input
                            className="piso-input"
                            type="number"
                            min={0}
                            max={4}
                            value={c.nota_minima}
                            onChange={(e) => patchCriterio(c.id, { nota_minima: Number(e.target.value) })}
                          />
                        </label>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
