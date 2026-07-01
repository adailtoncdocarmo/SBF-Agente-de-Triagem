import { useEffect, useState } from 'react'
import { AlertTriangle, Bell, BellOff, CheckCircle2, HelpCircle, Moon, Sun } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

import { listarNotificacoes, marcarLida } from '../api'
import { dataHora, tempoRelativo } from '../labels'
import type { Notificacao } from '../types'
import AjudaModal from './AjudaModal'

interface TopbarProps {
  tema: 'light' | 'dark'
  onAlternarTema: () => void
}

/** Escolhe o ícone do item conforme o tipo da notificação (concluída vs alerta). */
function iconeNotificacao(n: Notificacao): { Icone: typeof CheckCircle2; classe: string } {
  if (n.payload.taxa_auto_decisao !== undefined) return { Icone: CheckCircle2, classe: 'ok' }
  if (/não|nao|falh|erro/i.test(n.payload.titulo)) return { Icone: AlertTriangle, classe: 'alerta' }
  return { Icone: Bell, classe: 'info' }
}

/** Barra superior: ações (tema, ajuda, notificações com sino). */
export default function Topbar({ tema, onAlternarTema }: TopbarProps) {
  const navigate = useNavigate()

  const [notificacoes, setNotificacoes] = useState<Notificacao[]>([])
  const [aberto, setAberto] = useState(false)
  const [ajudaAberta, setAjudaAberta] = useState(false)

  useEffect(() => {
    const carregar = () => listarNotificacoes().then(setNotificacoes).catch(() => {})
    carregar()
    const timer = setInterval(carregar, 5000)
    return () => clearInterval(timer)
  }, [])

  const naoLidas = notificacoes.filter((n) => !n.lida).length

  async function abrirNotificacao(n: Notificacao) {
    setAberto(false)
    if (!n.lida) {
      await marcarLida(n.id).catch(() => {})
      setNotificacoes((atual) => atual.map((x) => (x.id === n.id ? { ...x, lida: true } : x)))
    }
    navigate(`/triagem/${n.lote_id}`)
  }

  return (
    <header className="topbar">
      <div className="topbar-actions">
        <button className="icon-button" onClick={onAlternarTema} aria-label="Alternar tema" title="Alternar tema">
          {tema === 'light' ? <Moon size={18} /> : <Sun size={18} />}
        </button>
        <button
          className="icon-button"
          aria-label="Ajuda"
          title="Como funciona a Triagem"
          onClick={() => setAjudaAberta(true)}
        >
          <HelpCircle size={18} />
        </button>
        <div className="sino-wrapper">
          <button
            className="icon-button"
            aria-label="Notificações"
            title="Notificações"
            onClick={() => setAberto((a) => !a)}
          >
            <Bell size={18} />
            {naoLidas > 0 && <span className="sino-badge">{naoLidas}</span>}
          </button>
          {aberto && (
            <div className="sino-dropdown elevation-3">
              <div className="sino-cabecalho">
                <span className="sino-titulo">Notificações</span>
                {naoLidas > 0 && <span className="sino-contador">{naoLidas} nova(s)</span>}
              </div>
              {notificacoes.length === 0 ? (
                <div className="sino-vazio">
                  <BellOff size={22} strokeWidth={1.6} />
                  <span>Nada por aqui ainda.</span>
                </div>
              ) : (
                <div className="sino-lista">
                  {notificacoes.slice(0, 8).map((n) => {
                    const { Icone, classe } = iconeNotificacao(n)
                    return (
                      <button
                        key={n.id}
                        className={`sino-item${n.lida ? '' : ' nao-lida'}`}
                        onClick={() => abrirNotificacao(n)}
                      >
                        <span className={`sino-item-icone ${classe}`}>
                          <Icone size={15} />
                        </span>
                        <span className="sino-item-corpo">
                          <strong className="sino-item-titulo">{n.payload.titulo}</strong>
                          {n.criado_em && (
                            <span className="sino-item-hora" title={tempoRelativo(n.criado_em)}>
                              {dataHora(n.criado_em)}
                            </span>
                          )}
                          <span className="sino-item-msg">{n.payload.mensagem}</span>
                          <span className="sino-item-link">Ver triagem →</span>
                        </span>
                      </button>
                    )
                  })}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      <AjudaModal aberto={ajudaAberta} onFechar={() => setAjudaAberta(false)} />
    </header>
  )
}
