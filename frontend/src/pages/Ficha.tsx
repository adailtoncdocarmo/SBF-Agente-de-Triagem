import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, CheckCircle2, Compass, FileText, ShieldAlert, Target } from 'lucide-react'

import PageHeader from '../components/PageHeader'
import Modal from '../components/Modal'
import { mensagemErro, obterFicha, urlCv } from '../api'
import {
  CONFIANCA_BADGE,
  CONFIANCA_LABEL,
  ESTADO_KO_BADGE,
  ESTADO_KO_LABEL,
  nomeExibicao,
  recoBadge,
  recoVerbo,
  STATUS_CRITICO_BADGE,
  STATUS_CRITICO_LABEL,
} from '../labels'
import type { FichaCandidato } from '../types'

export default function Ficha() {
  const { candidatoId } = useParams()
  const navigate = useNavigate()
  const [ficha, setFicha] = useState<FichaCandidato | null>(null)
  const [erro, setErro] = useState('')
  const [cvAberto, setCvAberto] = useState(false)

  useEffect(() => {
    obterFicha(Number(candidatoId))
      .then(setFicha)
      .catch((e) => setErro(mensagemErro(e)))
  }, [candidatoId])

  if (erro) return <div className="alerta-erro">{erro}</div>
  if (!ficha) return <p className="dica" style={{ padding: 24 }}>Carregando ficha…</p>

  const badge = recoBadge(ficha.recomendacao)
  const av = ficha.avaliacao
  // Zona (cor do círculo de score). Usa a zona da ficha; se ausente, deriva da
  // recomendação para casar com as cores do ranking.
  const zona =
    ficha.zona ??
    (ficha.recomendacao === 'avancar'
      ? 'entra'
      : ficha.recomendacao === 'nao_avancar'
        ? 'cai'
        : 'avaliar')

  return (
    <>
      <PageHeader
        titulo={nomeExibicao(ficha)}
        subtitulo={`${ficha.vaga} · ${ficha.nome_arquivo}`}
        acoes={
          <>
            <button
              className="btn btn-secondary"
              onClick={() => setCvAberto(true)}
              type="button"
              disabled={!ficha.cv_disponivel}
              title={
                ficha.cv_disponivel
                  ? 'Ver o currículo original'
                  : 'Currículo original indisponível. Reenvie o CV para visualizá-lo'
              }
            >
              <FileText size={16} /> Ver currículo
            </button>
            <button className="btn btn-ghost" onClick={() => navigate(-1)} type="button">
              <ArrowLeft size={16} /> Voltar
            </button>
          </>
        }
      />

      <Modal titulo={`Currículo de ${nomeExibicao(ficha)}`} aberto={cvAberto} onFechar={() => setCvAberto(false)} amplo>
        <iframe className="cv-viewer" src={urlCv(ficha.candidato_id)} title="Currículo do candidato" />
      </Modal>

      {/* Aderência + recomendação (campos explícitos do desafio) */}
      <div className="ficha-topo elevation-3">
        <div className={`cand-circ cand-circ-${zona} cand-circ-lg`}>
          <span className="cand-circ-num">{ficha.score_final.toFixed(0)}</span>
          <span className="cand-circ-lbl">de 100</span>
        </div>
        <div className="ficha-decisao">
          <div className="ficha-campo">
            <span className="ficha-campo-label">
              <Target size={14} /> Aderência ao perfil da vaga
            </span>
            <p className="ficha-justificativa">{ficha.justificativa}</p>
          </div>
          <div className="ficha-campo">
            <span className="ficha-campo-label">
              <Compass size={14} /> Recomendação
            </span>
            <div className="ficha-badges">
              <span className={`badge badge-grande ${badge.classe}`}>{recoVerbo(ficha.recomendacao)}</span>
              <span className={`badge ${CONFIANCA_BADGE[ficha.confianca]}`}>
                Confiança {CONFIANCA_LABEL[ficha.confianca]}
              </span>
            </div>
            {ficha.orientacao && <p className="ficha-justificativa">{ficha.orientacao}</p>}
          </div>
          {ficha.avaliacao.ressalvas.length > 0 && (
            <div className="ficha-campo ficha-campo-confirmar">
              <span className="ficha-campo-label">
                <ShieldAlert size={14} /> A confirmar
              </span>
              <div className="ficha-ressalvas">
                {ficha.avaliacao.ressalvas.map((r) => (
                  <span key={r} className="cand-sinal cand-sinal-ressalva">
                    <ShieldAlert size={12} /> {r}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="ficha-grid">
        {/* Destaques */}
        <div className="card elevation-2">
          <div className="card-header">
            <div className="card-title">
              <CheckCircle2 size={15} style={{ verticalAlign: '-2px', marginRight: 6 }} />
              Pontos de destaque
            </div>
          </div>
          <div className="card-body">
            {ficha.destaques.length ? (
              <ul className="lista-evidencias">
                {ficha.destaques.map((d, i) => (
                  <li key={i}>{d}</li>
                ))}
              </ul>
            ) : (
              <p className="dica">Sem evidências fortes destacadas.</p>
            )}
          </div>
        </div>

        {/* Lacunas + flags */}
        <div className="card elevation-2">
          <div className="card-header">
            <div className="card-title">
              <ShieldAlert size={15} style={{ verticalAlign: '-2px', marginRight: 6 }} />
              Pontos de atenção
            </div>
          </div>
          <div className="card-body">
            {ficha.lacunas.length ? (
              <ul className="lista-lacunas">
                {ficha.lacunas.map((l, i) => (
                  <li key={i}>{l}</li>
                ))}
              </ul>
            ) : (
              <p className="dica">Sem lacunas relevantes.</p>
            )}
            {av.flags.risco.length > 0 && (
              <div className="flags-risco">
                {av.flags.risco.map((f, i) => (
                  <div key={i} className="flag-item">
                    <span className={`badge ${f.severidade === 'baixa' ? 'neutral' : 'warning'}`}>
                      {f.severidade}
                    </span>
                    {f.descricao}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Portão 1 */}
      {av.portao_1.length > 0 && (
        <div className="card elevation-2" style={{ marginBottom: 'var(--space-4)' }}>
          <div className="card-header">
            <div className="card-title">Requisitos da vaga</div>
          </div>
          <div className="card-body">
            {av.portao_1.map((k, i) => (
              <div key={i} className="portao-linha">
                <span className={`badge ${ESTADO_KO_BADGE[k.estado]}`}>
                  {ESTADO_KO_LABEL[k.estado]}
                </span>
                <span>{k.requisito}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Breakdown dos 7 critérios */}
      <div className="card elevation-2">
        <div className="card-header">
          <div className="card-title">Detalhamento da avaliação</div>
          <div className="card-subtitle">nota 0-4 dada pela IA · pontuação calculada de forma determinística</div>
        </div>
        <div className="card-body">
          <table className="tabela-criterios">
            <thead>
              <tr>
                <th>Critério</th>
                <th>Nota</th>
                <th>Peso</th>
                <th>Pontos</th>
                <th>Crítico</th>
                <th title="Recência da competência: −1 ponto quando está defasada (sem uso há anos). Só afeta competências técnicas e experiência.">
                  Atualidade
                </th>
                <th className="col-porque" title="Por que a IA atribuiu essa nota ao critério.">Por quê</th>
              </tr>
            </thead>
            <tbody>
              {av.criterios.map((c) => (
                <tr key={c.criterio}>
                  <td>
                    <strong>{c.rotulo}</strong>
                  </td>
                  <td className="score-cell">{c.nota_0_4}</td>
                  <td>{c.peso}</td>
                  <td className="score-cell">{c.pontuacao.toFixed(1)}</td>
                  <td>
                    {c.critico ? (
                      <span className={`badge ${STATUS_CRITICO_BADGE[c.status_critico]}`}>
                        {STATUS_CRITICO_LABEL[c.status_critico]}
                      </span>
                    ) : (
                      '—'
                    )}
                  </td>
                  <td>
                    {c.recencia.modificador < 0 ? (
                      <span
                        className="badge warning"
                        title={`Competência defasada${c.recencia.ultimo_uso ? ` (último uso ${c.recencia.ultimo_uso})` : ''}: perdeu 1 ponto.`}
                      >
                        Defasada −1
                      </span>
                    ) : c.recencia.ultimo_uso ? (
                      <span className="badge success" title="Competência em uso recente.">
                        Atual
                      </span>
                    ) : (
                      '—'
                    )}
                  </td>
                  <td className="criterio-porque">
                    {c.justificativa_nota || c.evidencias[0] || '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  )
}
