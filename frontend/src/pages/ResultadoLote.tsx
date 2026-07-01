import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'

import PageHeader from '../components/PageHeader'
import ProgressoLote from '../components/ProgressoLote'
import RankingCandidatos from '../components/RankingCandidatos'
import { rankingVaga, statusLote } from '../api'
import type { RankingVaga, StatusLoteResposta } from '../types'

export default function ResultadoLote() {
  const { loteId } = useParams()
  const navigate = useNavigate()
  const id = Number(loteId)
  const [status, setStatus] = useState<StatusLoteResposta | null>(null)
  const [ranking, setRanking] = useState<RankingVaga | null>(null)
  const [erroRanking, setErroRanking] = useState(false)
  const [tentativa, setTentativa] = useState(0)

  useEffect(() => {
    let ativo = true
    let timer: ReturnType<typeof setInterval> | undefined
    const parar = () => {
      if (timer !== undefined) clearInterval(timer)
      timer = undefined
    }
    const carregar = async () => {
      try {
        const st = await statusLote(id)
        if (!ativo) return
        setStatus(st)
        // Estados terminais encerram o polling SEMPRE (mesmo se o ranking falhar)
        // — assim a tela nunca fica presa em "Processando…".
        if (st.status === 'concluido') {
          parar()
          try {
            const rk = await rankingVaga(st.vaga_id)
            if (!ativo) return
            setRanking(rk)
            setErroRanking(false)
          } catch {
            if (ativo) setErroRanking(true)
          }
        } else if (st.status === 'erro') {
          parar()
        }
      } catch {
        /* lote pode ainda não existir; tenta de novo no próximo tick */
      }
    }
    carregar()
    timer = setInterval(carregar, 2500)
    return () => {
      ativo = false
      parar()
    }
  }, [id, tentativa])

  const erro = status?.status === 'erro'
  const concluido = status?.status === 'concluido' && ranking
  const concluidoSemRanking = status?.status === 'concluido' && !ranking && erroRanking

  return (
    <>
      <PageHeader
        titulo={ranking?.vaga ?? 'Resultado da triagem'}
        subtitulo="Candidatos avaliados, ranqueados do mais ao menos aderente à vaga."
        acoes={
          <button className="btn btn-ghost" onClick={() => navigate('/')} type="button">
            <ArrowLeft size={16} /> Triagem
          </button>
        }
      />

      {erro && (
        <div className="alerta-erro">
          O processamento deste lote falhou
          {status ? ` (${status.concluidos}/${status.total} concluídos antes da falha)` : ''}. Volte
          à Triagem e reenvie os currículos; se persistir, verifique a chave de API em
          Configurações.
        </div>
      )}

      {!concluido && !erro && !concluidoSemRanking && (
        <ProgressoLote
          texto="Avaliando currículos com a IA…"
          concluidos={status?.concluidos}
          total={status?.total}
        />
      )}

      {concluidoSemRanking && (
        <div className="card elevation-2">
          <div className="card-body" style={{ textAlign: 'center' }}>
            <p style={{ marginBottom: 12 }}>
              Triagem concluída, mas não foi possível carregar o ranking agora.
            </p>
            <button
              className="btn btn-primary"
              type="button"
              onClick={() => {
                setErroRanking(false)
                setTentativa((t) => t + 1)
              }}
            >
              Tentar novamente
            </button>
          </div>
        </div>
      )}

      {concluido && ranking && <RankingCandidatos ranking={ranking} />}
    </>
  )
}
