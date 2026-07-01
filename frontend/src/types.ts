// Tipos TS que espelham os schemas Pydantic do backend (contratos da API).

export type ZonaDecisao = 'entra' | 'avaliar' | 'cai'
export type Recomendacao = 'avancar' | 'avaliar' | 'nao_avancar'
export type Confianca = 'alta' | 'media' | 'baixa'
export type EstadoKnockout = 'atende' | 'nao_atende' | 'nao_evidenciado'
export type StatusCritico = 'aprovado' | 'reprovado' | 'validacao' | 'nao_aplicavel'
export type Severidade = 'baixa' | 'media' | 'alta' | 'critica'
export type Volatilidade = 'alta' | 'media' | 'baixa'

export interface CriterioRegua {
  id: string
  rotulo: string
  peso: number
  e_critico: boolean
  nota_minima: number
}
export interface Knockout {
  requisito: string
  objetivo: boolean
  tipico_no_cv: boolean
  justificativa_job_related: string
}
export interface VolatilidadeCompetencia {
  competencia: string
  volatilidade: Volatilidade
}
export interface Thresholds {
  corte_verde: number
  corte_amarelo: number
  alvo_auto_decisao: number
  // legados (réguas antigas) — não decidem mais a zona
  percentil_shortlist?: number
  piso_absoluto?: number
}
export interface Regua {
  criterios: CriterioRegua[]
  knockouts: Knockout[]
  volatilidades: VolatilidadeCompetencia[]
  thresholds: Thresholds
  congelada: boolean
}

export interface ReprocessoInfo {
  modo: 'deterministico' | 'ia' | null
  afetados: number
  reprocessado: boolean
}
export type StatusVaga = 'ativa' | 'arquivada'
export interface VagaResposta {
  id: number
  titulo: string
  descricao: string
  congelada: boolean
  status: StatusVaga
  total_avaliados: number
  regua: Regua
  reprocesso?: ReprocessoInfo | null
}
export interface VagaResumo {
  id: number
  titulo: string
  congelada: boolean
  status: StatusVaga
  total_avaliados: number
}

export interface LoteCriado {
  lote_id: number
  total: number
}
export interface StatusLoteResposta {
  lote_id: number
  vaga_id: number
  status: string
  total: number
  concluidos: number
  taxa_auto_decisao: number | null
}
export interface LinhaRanking {
  candidato_id: number
  id_anonimo: string
  nome_arquivo: string
  nome_candidato: string | null
  posicao: number
  score_final: number
  percentil: number | null
  recomendacao: Recomendacao | null
  confianca: Confianca
  zona: ZonaDecisao | null
  sinais_fortes: string[]
  n_flags: number
  ressalvas: string[]
}
export interface FalhaCandidato {
  candidato_id: number
  id_anonimo: string
  nome_arquivo: string
  nome_candidato: string | null
  motivo: string
}
export interface ContagensZona {
  entra: number
  avaliar: number
  cai: number
}
export interface RankingVaga {
  vaga_id: number
  vaga: string
  total_avaliados: number
  taxa_auto_decisao: number
  contagens: ContagensZona
  linhas: LinhaRanking[]
  falhas: FalhaCandidato[]
}

export interface KnockoutAvaliado {
  requisito: string
  estado: EstadoKnockout
  evidencias: string[]
}
export interface RecenciaCalculada {
  volatilidade: Volatilidade
  ultimo_uso: string | null
  modificador: number
}
export interface CriterioAvaliado {
  criterio: string
  rotulo: string
  critico: boolean
  peso: number
  nota_0_4: number
  nota_minima: number
  status_critico: StatusCritico
  confianca_criterio: Confianca
  recencia: RecenciaCalculada
  pontuacao: number
  justificativa_nota: string
  evidencias: string[]
  lacunas: string[]
}
export interface FlagRisco {
  descricao: string
  severidade: Severidade
  acao: string
}
export interface Avaliacao {
  candidato: string
  vaga: string
  versao_framework: string
  portao_1: KnockoutAvaliado[]
  criterios: CriterioAvaliado[]
  score_final: number
  calibracao_lote: { percentil: number; piso_absoluto: number; empate_tecnico: boolean; comparacao_direta: boolean } | null
  flags: { risco: FlagRisco[]; clareza: { nivel: Confianca; confianca_avaliacao: Confianca } }
  zona_decisao: ZonaDecisao | null
  rejeicao_automatica_permitida: boolean
  motivo_zona: string
  ressalvas: string[]
  recomendacao: Recomendacao | null
  confianca: Confianca
  sintese_aderencia?: string
  sintese_recomendacao?: string
}
export interface FichaCandidato {
  candidato_id: number
  id_anonimo: string
  nome_candidato: string | null
  nome_arquivo: string
  vaga: string
  posicao: number | null
  total_lote: number | null
  score_final: number
  percentil: number | null
  recomendacao: Recomendacao | null
  confianca: Confianca
  zona: ZonaDecisao | null
  justificativa: string
  orientacao: string
  destaques: string[]
  lacunas: string[]
  cv_disponivel: boolean
  avaliacao: Avaliacao
}

export interface Notificacao {
  id: number
  lote_id: number
  lida: boolean
  payload: { titulo: string; mensagem: string; link?: string; taxa_auto_decisao?: number }
  criado_em?: string | null
}

export interface CustoEstagio {
  estagio: string
  chamadas: number
  custo_usd: number
  custo_brl: number
  latencia_media_ms: number
}
export interface MetricasOperacionais {
  lotes_concluidos: number
  cvs_avaliados: number
  taxa_auto_decisao_media: number
  alvo_auto_decisao: number
  distribuicao_zonas: { entra: number; avaliar: number; cai: number }
  custo_total_usd: number
  custo_total_brl: number
  custo_medio_por_cv_usd: number
  custo_medio_por_cv_brl: number
  taxa_usd_brl: number
  chamadas_api: number
  latencia_media_ms: number
  latencia_p95_ms: number
  cache_hit_ratio: number
  custo_por_estagio: CustoEstagio[]
}
export type ProvedorIA = 'anthropic' | 'openai' | 'gemini'
export interface ProvedorSnapshot {
  provedor: ProvedorIA
  modelo: string
  api_key_configurada: boolean
  api_key_mascarada: string
  habilitado?: boolean
}
export interface ConfiguracaoSnapshot {
  api_key_configurada: boolean
  principal: ProvedorSnapshot
  secundaria: ProvedorSnapshot & { habilitado: boolean }
  thresholds: { percentil_shortlist: number; piso_absoluto: number; alvo_auto_decisao: number }
  concorrencia_cvs: number
  timeout_llm: number
}
export interface TesteChave {
  ok: boolean
  mensagem: string
}
