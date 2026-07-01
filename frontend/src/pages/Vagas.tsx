import { useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  Archive,
  ArchiveRestore,
  Briefcase,
  LayoutGrid,
  List,
  Plus,
  Save,
  SlidersHorizontal,
  Sparkles,
  Upload,
  Users,
} from 'lucide-react'

import PageHeader from '../components/PageHeader'
import ProgressoLote from '../components/ProgressoLote'
import RankingCandidatos from '../components/RankingCandidatos'
import ReguaEditor from '../components/ReguaEditor'
import {
  arquivarVaga,
  criarLote,
  criarVaga,
  listarVagas,
  mensagemErro,
  obterVaga,
  rankingVaga,
  restaurarVaga,
  salvarRegua,
} from '../api'
import { itemPorPath } from '../nav'
import type { RankingVaga, Regua, StatusVaga, VagaResposta, VagaResumo } from '../types'

type Aba = 'candidatos' | 'parametros'
type Visao = 'cards' | 'lista'

/**
 * Espelha `precisa_reextrair` do backend: mudar rótulos de critério ou knockouts
 * exige reextração com IA; pesos/cortes/pisos são recálculo determinístico.
 * Usado só para escolher a mensagem do modal — o backend decide de fato.
 */
function precisaReextrair(antiga: Regua, nova: Regua): boolean {
  const rotulos = (r: Regua) =>
    JSON.stringify(r.criterios.map((c) => [c.id, c.rotulo]).sort())
  const knockouts = (r: Regua) =>
    JSON.stringify(r.knockouts.map((k) => [k.requisito, k.justificativa_job_related]))
  return rotulos(antiga) !== rotulos(nova) || knockouts(antiga) !== knockouts(nova)
}

export default function Vagas() {
  const meta = itemPorPath('/vagas')
  const navigate = useNavigate()

  const [vagas, setVagas] = useState<VagaResumo[]>([])
  const [criandoNova, setCriandoNova] = useState(false)
  const [titulo, setTitulo] = useState('')
  const [descricao, setDescricao] = useState('')
  const [vagaAtual, setVagaAtual] = useState<VagaResposta | null>(null)
  const [regua, setRegua] = useState<Regua | null>(null)
  const [reguaOriginal, setReguaOriginal] = useState<Regua | null>(null)
  const [carregando, setCarregando] = useState(false)
  const [erro, setErro] = useState('')
  const [aviso, setAviso] = useState('')
  const [modalAberto, setModalAberto] = useState(false)
  const [aba, setAba] = useState<Aba>('candidatos')
  const [ranking, setRanking] = useState<RankingVaga | null>(null)
  const inputArquivos = useRef<HTMLInputElement>(null)
  const [searchParams, setSearchParams] = useSearchParams()
  // Visão da lista de vagas (cartões/lista) — preferência persistida.
  const [visao, setVisao] = useState<Visao>(
    () => (localStorage.getItem('vagas_visao') as Visao) || 'cards',
  )
  // Filtro de status: ativas (default) ou arquivadas.
  const [filtroStatus, setFiltroStatus] = useState<StatusVaga>('ativa')

  function escolherVisao(v: Visao) {
    setVisao(v)
    localStorage.setItem('vagas_visao', v)
  }

  useEffect(() => {
    listarVagas().then(setVagas).catch(() => setVagas([]))
  }, [])

  // A vaga aberta vive na URL (`/vagas?vaga=<id>`) — assim voltar da ficha de um
  // candidato (navigate(-1)) reabre a lista de candidatos certa, em vez de cair na
  // lista de vagas. Sem `?vaga`, mostra a lista.
  useEffect(() => {
    const param = searchParams.get('vaga')
    if (param) {
      const id = Number(param)
      if (!Number.isNaN(id) && id !== vagaAtual?.id) void abrirVaga(id)
    } else if (vagaAtual) {
      setVagaAtual(null)
      setRegua(null)
      setReguaOriginal(null)
      setRanking(null)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams])

  const somaPesos = regua?.criterios.reduce((a, c) => a + c.peso, 0) ?? 0
  const nCriticos = regua?.criterios.filter((c) => c.e_critico).length ?? 0
  const podeCongelar = !!regua && somaPesos === 100 && nCriticos >= 1 && nCriticos <= 3

  async function gerarRegua() {
    setErro('')
    if (!titulo.trim() || !descricao.trim()) {
      setErro('Preencha título e descrição da vaga.')
      return
    }
    setCarregando(true)
    try {
      const vaga = await criarVaga(titulo, descricao)
      setVagaAtual(vaga)
      setRegua(vaga.regua)
      setReguaOriginal(vaga.regua)
      setAba('parametros') // vaga nova: começa nos critérios (ainda sem candidatos)
      rankingVaga(vaga.id).then(setRanking).catch(() => setRanking(null))
      setCriandoNova(false)
      // Recarrega a lista para a vaga nova já aparecer ao voltar para a Triagem.
      setVagas(await listarVagas())
    } catch (e) {
      setErro(mensagemErro(e))
    } finally {
      setCarregando(false)
    }
  }

  async function abrirVaga(id: number) {
    setErro('')
    setCarregando(true)
    try {
      const vaga = await obterVaga(id)
      setVagaAtual(vaga)
      setRegua(vaga.regua)
      setReguaOriginal(vaga.regua)
      // Candidatos é a primeira informação quando já há gente avaliada.
      setAba(vaga.total_avaliados > 0 ? 'candidatos' : 'parametros')
      setRanking(null)
      rankingVaga(id).then(setRanking).catch(() => setRanking(null))
    } catch (e) {
      setErro(mensagemErro(e))
    } finally {
      setCarregando(false)
    }
  }

  // Salvar dispara o modal só quando já há candidatos avaliados (reprocesso real).
  function aoClicarSalvar() {
    if (!vagaAtual || !regua) return
    if (vagaAtual.total_avaliados > 0) {
      setModalAberto(true)
    } else {
      void salvar()
    }
  }

  async function salvar() {
    if (!vagaAtual || !regua) return
    setModalAberto(false)
    setCarregando(true)
    setErro('')
    setAviso('')
    try {
      const vaga = await salvarRegua(vagaAtual.id, regua)
      setVagaAtual(vaga)
      setRegua(vaga.regua)
      setReguaOriginal(vaga.regua)
      setVagas(await listarVagas())
      const r = vaga.reprocesso
      if (r?.reprocessado && r.modo === 'deterministico') {
        setAviso(`Critérios salvos. ${r.afetados} candidato(s) reranqueados na hora (sem custo de IA).`)
        // Recarrega o ranking para refletir os novos scores na aba Candidatos.
        rankingVaga(vaga.id).then(setRanking).catch(() => {})
      } else if (r?.reprocessado && r.modo === 'ia') {
        setAviso(`Critérios salvos. Reprocessando ${r.afetados} currículo(s) com IA. Acompanhe na Triagem.`)
      } else {
        setAviso('Critérios salvos.')
      }
    } catch (e) {
      setErro(mensagemErro(e))
    } finally {
      setCarregando(false)
    }
  }

  // Modo do reprocesso para a mensagem do modal (o backend decide de fato).
  const modoReprocesso =
    reguaOriginal && regua && precisaReextrair(reguaOriginal, regua) ? 'ia' : 'deterministico'

  async function enviarLote(arquivos: FileList | null) {
    if (!vagaAtual || !arquivos || arquivos.length === 0) return
    setCarregando(true)
    setErro('')
    try {
      const resultado = await criarLote(vagaAtual.id, Array.from(arquivos))
      navigate(`/triagem/${resultado.lote_id}`)
    } catch (e) {
      setErro(mensagemErro(e))
    } finally {
      setCarregando(false)
    }
  }

  // Arquiva (ou restaura) uma vaga e recarrega a lista. `paraArquivar=true`
  // arquiva; `false` restaura. O chamador faz o stopPropagation quando preciso.
  async function alternarArquivo(id: number, paraArquivar: boolean) {
    setErro('')
    try {
      if (paraArquivar) await arquivarVaga(id)
      else await restaurarVaga(id)
      setVagas(await listarVagas())
    } catch (err) {
      setErro(mensagemErro(err))
    }
  }

  function voltar() {
    // Limpa o `?vaga` da URL; o efeito acima sincroniza o estado para a lista.
    if (searchParams.get('vaga')) setSearchParams({})
    setVagaAtual(null)
    setRegua(null)
    setReguaOriginal(null)
    setRanking(null)
    setAba('candidatos')
    setCriandoNova(false)
    setTitulo('')
    setDescricao('')
    setErro('')
    setAviso('')
    setModalAberto(false)
  }

  // --- Editor de uma vaga (régua sempre editável + upload) ---
  if (vagaAtual && regua) {
    const temAvaliados = vagaAtual.total_avaliados > 0
    return (
      <>
        <PageHeader
          titulo={vagaAtual.titulo}
          subtitulo={`${nCriticos} critério(s) decisivo(s)${
            temAvaliados ? ` · ${vagaAtual.total_avaliados} candidato(s) avaliados` : ''
          }`}
          acoes={
            <>
              {vagaAtual.status === 'arquivada' ? (
                <button
                  className="btn btn-secondary"
                  type="button"
                  onClick={async () => {
                    await alternarArquivo(vagaAtual.id, false)
                    voltar()
                  }}
                >
                  <ArchiveRestore size={16} /> Restaurar
                </button>
              ) : (
                <button
                  className="btn btn-secondary"
                  type="button"
                  onClick={async () => {
                    await alternarArquivo(vagaAtual.id, true)
                    voltar()
                  }}
                >
                  <Archive size={16} /> Arquivar
                </button>
              )}
              <button className="btn btn-ghost" onClick={voltar} type="button">
                Voltar
              </button>
            </>
          }
        />
        {erro && <div className="alerta-erro">{erro}</div>}
        {aviso && <div className="alerta-ok">{aviso}</div>}

        {/* Input de arquivos único — acionado pelo card grande (onboarding) ou
            pelo botão compacto da barra de abas (quando já há candidatos). */}
        <input
          ref={inputArquivos}
          type="file"
          multiple
          accept=".pdf,.txt"
          hidden
          onChange={(e) => enviarLote(e.target.files)}
        />

        <div className="abas-barra">
          <div className="abas">
            <button
              type="button"
              className={`aba ${aba === 'candidatos' ? 'ativa' : ''}`}
              onClick={() => setAba('candidatos')}
            >
              <Users size={15} /> Candidatos
              <span className="aba-contagem">{vagaAtual.total_avaliados}</span>
            </button>
            <button
              type="button"
              className={`aba ${aba === 'parametros' ? 'ativa' : ''}`}
              onClick={() => setAba('parametros')}
            >
              <SlidersHorizontal size={15} /> Parâmetros
            </button>
          </div>
          {aba === 'candidatos' && temAvaliados && (
            <button
              className="btn btn-primary btn-sm"
              disabled={carregando}
              onClick={() => inputArquivos.current?.click()}
              type="button"
            >
              <Upload size={16} /> {carregando ? 'Enviando...' : 'Selecionar currículos'}
            </button>
          )}
        </div>

        {aba === 'candidatos' && (
          <>
            {/* Onboarding (só sem candidatos): card grande convidando ao 1º envio. */}
            {!temAvaliados && (
              <div className="card elevation-2" style={{ marginBottom: 'var(--space-4)' }}>
                <div className="card-body">
                  <div className="upload-zona">
                    <Upload size={28} />
                    <p>
                      Envie os currículos (PDF ou .txt). Cada lote é somado ao pool da vaga e
                      todos os candidatos são reranqueados juntos.
                    </p>
                    <button
                      className="btn btn-primary"
                      disabled={carregando}
                      onClick={() => inputArquivos.current?.click()}
                      type="button"
                    >
                      <Upload size={16} /> {carregando ? 'Enviando...' : 'Selecionar currículos'}
                    </button>
                  </div>
                </div>
              </div>
            )}

            {ranking ? (
              <RankingCandidatos ranking={ranking} />
            ) : (
              <ProgressoLote texto="Carregando candidatos…" />
            )}
          </>
        )}

        {aba === 'parametros' && (
          <>
            <ReguaEditor key={vagaAtual.id} regua={regua} onChange={setRegua} />
            <div className="acoes-rodape">
              <button
                className="btn btn-primary"
                disabled={!podeCongelar || carregando}
                onClick={aoClicarSalvar}
                type="button"
              >
                <Save size={16} /> {carregando ? 'Salvando...' : 'Salvar critérios'}
              </button>
            </div>
          </>
        )}

        {modalAberto && (
          <div className="modal-overlay" onClick={() => setModalAberto(false)}>
            <div className="modal-card elevation-3" onClick={(e) => e.stopPropagation()}>
              <div className="modal-titulo">Reprocessar candidatos?</div>
              <p className="modal-texto">
                Salvar vai reprocessar os <strong>{vagaAtual.total_avaliados}</strong>{' '}
                currículo(s) já avaliados com os novos critérios.
              </p>
              <p className="modal-texto">
                {modoReprocesso === 'deterministico' ? (
                  <>
                    Como você mudou apenas pesos/cortes, o recálculo é{' '}
                    <strong>instantâneo e sem custo de IA</strong>: todos são reranqueados na
                    hora.
                  </>
                ) : (
                  <>
                    Como você mudou critérios ou requisitos obrigatórios, será necessária{' '}
                    <strong>reextração com IA</strong> de todos os currículos (gera custo e leva
                    alguns instantes).
                  </>
                )}
              </p>
              <div className="modal-acoes">
                <button className="btn btn-ghost" type="button" onClick={() => setModalAberto(false)}>
                  Cancelar
                </button>
                <button className="btn btn-primary" type="button" onClick={() => void salvar()}>
                  Salvar e reprocessar
                </button>
              </div>
            </div>
          </div>
        )}
      </>
    )
  }

  // --- Formulário de nova vaga ---
  if (criandoNova) {
    return (
      <>
        <PageHeader
          titulo="Nova vaga"
          subtitulo="Cole a descrição da vaga e a IA transforma em critérios de avaliação."
          acoes={
            <button className="btn btn-ghost" onClick={voltar} type="button">
              Cancelar
            </button>
          }
        />
        {erro && <div className="alerta-erro">{erro}</div>}
        <div className="card elevation-2">
          <div className="card-body form-vaga">
            <label className="campo">
              <span>Título da vaga</span>
              <input
                value={titulo}
                onChange={(e) => setTitulo(e.target.value)}
                placeholder="Ex.: Vendedor(a) de Loja (Operações de Varejo)"
              />
            </label>
            <label className="campo">
              <span>Descrição da vaga</span>
              <textarea
                rows={10}
                value={descricao}
                onChange={(e) => setDescricao(e.target.value)}
                placeholder="Cole aqui a descrição completa: responsabilidades, requisitos, disponibilidade..."
              />
            </label>
            <button
              className="btn btn-primary"
              disabled={carregando}
              onClick={gerarRegua}
              type="button"
            >
              <Sparkles size={16} /> {carregando ? 'Analisando vaga...' : 'Gerar critérios com IA'}
            </button>
          </div>
        </div>
      </>
    )
  }

  // --- Lista de vagas ---
  const ativas = vagas.filter((v) => v.status === 'ativa')
  const arquivadas = vagas.filter((v) => v.status === 'arquivada')
  const vagasFiltradas = filtroStatus === 'ativa' ? ativas : arquivadas

  function abrirVagaPorClique(id: number) {
    setSearchParams({ vaga: String(id) })
  }

  return (
    <>
      <PageHeader
        titulo={meta.label}
        subtitulo={meta.subtitulo}
        acoes={
          <button className="btn btn-primary" onClick={() => setCriandoNova(true)} type="button">
            <Plus size={16} /> Nova vaga
          </button>
        }
      />
      {erro && <div className="alerta-erro">{erro}</div>}
      {vagas.length === 0 ? (
        <div className="empty-state elevation-2">
          <div className="empty-icon">
            <Briefcase strokeWidth={1.6} />
          </div>
          <div className="empty-title">Nenhuma vaga ainda</div>
          <p className="empty-desc">
            Cadastre a primeira vaga: cole a descrição e a IA monta os critérios de avaliação.
          </p>
        </div>
      ) : (
        <>
          <div className="vagas-toolbar">
            <div className="rigor-seg vagas-filtro">
              <button
                type="button"
                className={`rigor-opcao ${filtroStatus === 'ativa' ? 'ativo' : ''}`}
                onClick={() => setFiltroStatus('ativa')}
              >
                Ativas <span className="seg-contagem">{ativas.length}</span>
              </button>
              <button
                type="button"
                className={`rigor-opcao ${filtroStatus === 'arquivada' ? 'ativo' : ''}`}
                onClick={() => setFiltroStatus('arquivada')}
              >
                Arquivadas <span className="seg-contagem">{arquivadas.length}</span>
              </button>
            </div>
            <div className="view-toggle">
              <button
                type="button"
                className={`view-opcao ${visao === 'cards' ? 'ativo' : ''}`}
                onClick={() => escolherVisao('cards')}
                title="Ver em cartões"
                aria-label="Ver em cartões"
              >
                <LayoutGrid size={16} />
              </button>
              <button
                type="button"
                className={`view-opcao ${visao === 'lista' ? 'ativo' : ''}`}
                onClick={() => escolherVisao('lista')}
                title="Ver em lista"
                aria-label="Ver em lista"
              >
                <List size={16} />
              </button>
            </div>
          </div>

          {vagasFiltradas.length === 0 ? (
            <p className="dica" style={{ padding: 'var(--space-4)' }}>
              {filtroStatus === 'ativa'
                ? 'Nenhuma vaga ativa. Cadastre uma nova ou restaure uma arquivada.'
                : 'Nenhuma vaga arquivada.'}
            </p>
          ) : visao === 'cards' ? (
            <div className="lista-cards">
              {vagasFiltradas.map((v) => (
                <div
                  key={v.id}
                  className="vaga-card elevation-2"
                  role="button"
                  tabIndex={0}
                  onClick={() => abrirVagaPorClique(v.id)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      abrirVagaPorClique(v.id)
                    }
                  }}
                >
                  <div className="vaga-card-icone">
                    <Briefcase size={18} />
                  </div>
                  <div className="vaga-card-info">
                    <div className="vaga-card-titulo">{v.titulo}</div>
                    <span className="vaga-card-contagem">
                      <Users size={13} style={{ verticalAlign: '-2px', marginRight: 4 }} />
                      {v.total_avaliados > 0
                        ? `${v.total_avaliados} candidato(s) avaliados`
                        : 'Sem candidatos ainda'}
                    </span>
                  </div>
                  <button
                    className="icon-button vaga-arquivar"
                    type="button"
                    title={v.status === 'ativa' ? 'Arquivar vaga' : 'Restaurar vaga'}
                    aria-label={v.status === 'ativa' ? 'Arquivar vaga' : 'Restaurar vaga'}
                    onClick={(e) => {
                      e.stopPropagation()
                      void alternarArquivo(v.id, v.status === 'ativa')
                    }}
                  >
                    {v.status === 'ativa' ? <Archive size={16} /> : <ArchiveRestore size={16} />}
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <div className="vaga-lista">
              {vagasFiltradas.map((v) => (
                <div
                  key={v.id}
                  className="vaga-row elevation-1"
                  role="button"
                  tabIndex={0}
                  onClick={() => abrirVagaPorClique(v.id)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      abrirVagaPorClique(v.id)
                    }
                  }}
                >
                  <div className="vaga-row-icone">
                    <Briefcase size={16} />
                  </div>
                  <span className="vaga-row-titulo">{v.titulo}</span>
                  <span className="vaga-row-contagem">
                    <Users size={13} style={{ verticalAlign: '-2px', marginRight: 4 }} />
                    {v.total_avaliados > 0 ? `${v.total_avaliados} avaliados` : 'Sem candidatos'}
                  </span>
                  <span className={`badge ${v.status === 'ativa' ? 'success' : 'neutral'}`}>
                    {v.status === 'ativa' ? 'Ativa' : 'Arquivada'}
                  </span>
                  <button
                    className="icon-button vaga-arquivar"
                    type="button"
                    title={v.status === 'ativa' ? 'Arquivar vaga' : 'Restaurar vaga'}
                    aria-label={v.status === 'ativa' ? 'Arquivar vaga' : 'Restaurar vaga'}
                    onClick={(e) => {
                      e.stopPropagation()
                      void alternarArquivo(v.id, v.status === 'ativa')
                    }}
                  >
                    {v.status === 'ativa' ? <Archive size={16} /> : <ArchiveRestore size={16} />}
                  </button>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </>
  )
}
