import { useEffect, useState } from 'react'
import { KeyRound, PlugZap, Save, ShieldCheck, Trash2 } from 'lucide-react'

import PageHeader from '../components/PageHeader'
import {
  mensagemErro,
  obterConfiguracao,
  removerChave,
  salvarConfiguracao,
  testarChave,
} from '../api'
import { itemPorPath } from '../nav'
import type { ConfiguracaoSnapshot, ProvedorIA } from '../types'

const PROVEDORES: { valor: ProvedorIA; label: string }[] = [
  { valor: 'anthropic', label: 'Claude (Anthropic)' },
  { valor: 'openai', label: 'OpenAI' },
  { valor: 'gemini', label: 'Google Gemini' },
]
const MODELOS_SUGERIDOS: Record<ProvedorIA, string[]> = {
  anthropic: ['claude-haiku-4-5', 'claude-sonnet-4-6', 'claude-opus-4-8'],
  openai: ['gpt-4o-mini', 'gpt-4o', 'gpt-4.1-mini'],
  gemini: ['gemini-2.0-flash', 'gemini-1.5-pro'],
}

/**
 * Configurações enxutas (POC): as chaves de API. Os critérios e o rigor da
 * seleção ficam dentro de cada vaga (aba Parâmetros). A chave **reserva** dá
 * resiliência: se a principal falhar/atrasar, o sistema usa a reserva
 * automaticamente — a fila não trava.
 */
export default function Configuracoes() {
  const meta = itemPorPath('/configuracoes')
  const [snap, setSnap] = useState<ConfiguracaoSnapshot | null>(null)
  const [msg, setMsg] = useState('')
  const [erro, setErro] = useState('')

  // Slot Principal
  const [pProvedor, setPProvedor] = useState<ProvedorIA>('anthropic')
  const [pModelo, setPModelo] = useState('')
  const [pChave, setPChave] = useState('')
  // Slot Reserva (failover)
  const [sHabilitado, setSHabilitado] = useState(false)
  const [sProvedor, setSProvedor] = useState<ProvedorIA>('openai')
  const [sModelo, setSModelo] = useState('')
  const [sChave, setSChave] = useState('')

  function aplicarSnap(s: ConfiguracaoSnapshot) {
    setSnap(s)
    setPProvedor(s.principal.provedor)
    setPModelo(s.principal.modelo)
    setSHabilitado(s.secundaria.habilitado)
    setSProvedor(s.secundaria.provedor)
    setSModelo(s.secundaria.modelo)
  }

  async function recarregar() {
    aplicarSnap(await obterConfiguracao())
  }
  useEffect(() => {
    recarregar().catch((e) => setErro(mensagemErro(e)))
  }, [])

  async function salvar(parcial: Record<string, unknown>, ok: string) {
    setMsg('')
    setErro('')
    try {
      aplicarSnap(await salvarConfiguracao(parcial))
      setMsg(ok)
    } catch (e) {
      setErro(mensagemErro(e))
    }
  }

  async function testar(provedor: ProvedorIA, chave: string) {
    setMsg('Testando conexão…')
    setErro('')
    try {
      const r = await testarChave(provedor, chave || undefined)
      if (r.ok) setMsg(r.mensagem)
      else {
        setMsg('')
        setErro(r.mensagem)
      }
    } catch (e) {
      setMsg('')
      setErro(mensagemErro(e))
    }
  }

  async function remover(slot: 'principal' | 'secundaria', ok: string) {
    setMsg('')
    setErro('')
    try {
      aplicarSnap(await removerChave(slot))
      if (slot === 'principal') setPChave('')
      else setSChave('')
      setMsg(ok)
    } catch (e) {
      setErro(mensagemErro(e))
    }
  }

  if (!snap) {
    return (
      <>
        <PageHeader titulo={meta.label} subtitulo={meta.subtitulo} />
        {erro ? (
          <div className="alerta-erro">
            Não foi possível carregar: {erro}. Verifique se o backend está no ar e atualizado.
            <div style={{ marginTop: 'var(--space-3)' }}>
              <button
                className="btn btn-secondary"
                type="button"
                onClick={() => {
                  setErro('')
                  recarregar().catch((e) => setErro(mensagemErro(e)))
                }}
              >
                Tentar novamente
              </button>
            </div>
          </div>
        ) : (
          <p className="dica" style={{ padding: 24 }}>Carregando configurações…</p>
        )}
      </>
    )
  }

  return (
    <>
      <PageHeader titulo={meta.label} subtitulo="As chaves de API que ativam a triagem. A reserva entra sozinha se a principal falhar." />
      <div
        className={`alerta-ok ${snap.api_key_configurada ? '' : 'pendente'}`}
        style={!snap.api_key_configurada ? { background: 'var(--status-warning-soft)', color: 'var(--status-warning)' } : undefined}
      >
        {snap.api_key_configurada
          ? '✓ Sistema pronto: chave de API principal configurada.'
          : 'Cole a chave de API principal abaixo para ativar a triagem.'}
      </div>
      {msg && <div className="alerta-ok">{msg}</div>}
      {erro && <div className="alerta-erro">{erro}</div>}

      <div className="cfg-cols">
        {/* Chave principal */}
        <section className="card elevation-2">
          <div className="card-header">
            <div className="card-title">
              <KeyRound size={15} style={{ verticalAlign: '-2px', marginRight: 6 }} />
              Chave de API principal
            </div>
            <span className={`badge ${snap.principal.api_key_configurada ? 'success' : 'warning'}`}>
              {snap.principal.api_key_configurada ? 'Configurada' : 'Pendente'}
            </span>
          </div>
          <div className="card-body">
            <CamposChave
              provedor={pProvedor}
              setProvedor={setPProvedor}
              modelo={pModelo}
              setModelo={setPModelo}
              chave={pChave}
              setChave={setPChave}
              mascarada={snap.principal.api_key_mascarada}
            />
            <div className="cfg-acoes">
              <button
                className="btn btn-primary"
                type="button"
                onClick={() =>
                  salvar(
                    { principal: { provedor: pProvedor, modelo: pModelo, api_key: pChave } },
                    'Chave principal salva.',
                  ).then(() => setPChave(''))
                }
              >
                <Save size={16} /> Salvar
              </button>
              <button className="btn btn-secondary" type="button" onClick={() => testar(pProvedor, pChave)}>
                <PlugZap size={16} /> Testar
              </button>
              <button
                className="btn btn-secondary"
                type="button"
                disabled={!snap.principal.api_key_configurada}
                onClick={() => remover('principal', 'Chave principal removida.')}
              >
                <Trash2 size={16} /> Remover
              </button>
            </div>
            <p className="dica" style={{ marginTop: 'var(--space-2)' }}>
              Para trocar, cole a nova chave e clique em Salvar. Para excluir, use Remover.
            </p>
          </div>
        </section>

        {/* Chave reserva (failover) */}
        <section className="card elevation-2">
          <div className="card-header">
            <div>
              <div className="card-title">
                <ShieldCheck size={15} style={{ verticalAlign: '-2px', marginRight: 6 }} />
                Chave de API reserva
              </div>
              <div className="card-subtitle">
                Se a principal falhar ou atrasar, o sistema usa esta automaticamente, sem travar a fila.
              </div>
            </div>
            <span className={`badge ${sHabilitado ? 'success' : 'neutral'}`}>
              {sHabilitado ? 'Ativa' : 'Desligada'}
            </span>
          </div>
          <div className="card-body">
            <label className="check" style={{ marginBottom: 'var(--space-3)' }}>
              <input type="checkbox" checked={sHabilitado} onChange={(e) => setSHabilitado(e.target.checked)} />
              Ativar reserva (usar se a principal falhar)
            </label>
            <CamposChave
              provedor={sProvedor}
              setProvedor={setSProvedor}
              modelo={sModelo}
              setModelo={setSModelo}
              chave={sChave}
              setChave={setSChave}
              mascarada={snap.secundaria.api_key_mascarada}
            />
            <div className="cfg-acoes">
              <button
                className="btn btn-primary"
                type="button"
                onClick={() =>
                  salvar(
                    { secundaria: { habilitado: sHabilitado, provedor: sProvedor, modelo: sModelo, api_key: sChave } },
                    'Reserva salva.',
                  ).then(() => setSChave(''))
                }
              >
                <Save size={16} /> Salvar
              </button>
              <button className="btn btn-secondary" type="button" onClick={() => testar(sProvedor, sChave)}>
                <PlugZap size={16} /> Testar
              </button>
              <button
                className="btn btn-secondary"
                type="button"
                disabled={!snap.secundaria.api_key_configurada}
                onClick={() => remover('secundaria', 'Chave reserva removida.')}
              >
                <Trash2 size={16} /> Remover
              </button>
            </div>
            <p className="dica" style={{ marginTop: 'var(--space-2)' }}>
              Pode ser de outro provedor (ex.: OpenAI como reserva do Claude). Teste sem ativar; ative para
              que ela entre sozinha se a principal falhar.
            </p>
          </div>
        </section>
      </div>

      <p className="dica" style={{ marginTop: 'var(--space-4)' }}>
        As chaves ficam guardadas localmente e são exibidas mascaradas, adequado para demonstração. Em
        produção, use um cofre de segredos.
      </p>
    </>
  )
}

interface CamposChaveProps {
  provedor: ProvedorIA
  setProvedor: (p: ProvedorIA) => void
  modelo: string
  setModelo: (m: string) => void
  chave: string
  setChave: (c: string) => void
  mascarada: string
}

/** Trio reutilizável: provedor + chave (mascarada) + modelo. */
function CamposChave({ provedor, setProvedor, modelo, setModelo, chave, setChave, mascarada }: CamposChaveProps) {
  return (
    <>
      <label className="campo">
        <span>Provedor de IA</span>
        <select
          value={provedor}
          onChange={(e) => {
            const novo = e.target.value as ProvedorIA
            setProvedor(novo)
            setModelo(MODELOS_SUGERIDOS[novo][0])
          }}
        >
          {PROVEDORES.map((p) => (
            <option key={p.valor} value={p.valor}>
              {p.label}
            </option>
          ))}
        </select>
      </label>
      <label className="campo">
        <span>
          Chave de API {mascarada && <em className="dica">(atual: {mascarada})</em>}
        </span>
        <input
          type="password"
          value={chave}
          onChange={(e) => setChave(e.target.value)}
          placeholder={mascarada ? 'deixe em branco para manter a atual' : 'cole a chave aqui'}
        />
      </label>
      <label className="campo">
        <span>Modelo</span>
        <input value={modelo} onChange={(e) => setModelo(e.target.value)} placeholder={MODELOS_SUGERIDOS[provedor][0]} />
        <div className="sugestoes-modelo">
          {MODELOS_SUGERIDOS[provedor].map((m) => (
            <button
              key={m}
              type="button"
              className={`chip-modelo${modelo === m ? ' ativo' : ''}`}
              onClick={() => setModelo(m)}
            >
              {m}
            </button>
          ))}
        </div>
      </label>
    </>
  )
}
