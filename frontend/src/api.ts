import axios from 'axios'

import type {
  ConfiguracaoSnapshot,
  FichaCandidato,
  LoteCriado,
  MetricasOperacionais,
  Notificacao,
  RankingVaga,
  Regua,
  StatusLoteResposta,
  TesteChave,
  VagaResposta,
  VagaResumo,
} from './types'

// O FastAPI serve a API sob "/api" (mesmo host em produção; em dev o Vite faz
// proxy para :8000). A geração da régua chama a IA e pode demorar — timeout largo.
export const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
  timeout: 120_000,
})

// --- Vagas ---
export async function listarVagas(): Promise<VagaResumo[]> {
  const { data } = await api.get<VagaResumo[]>('/vagas')
  return data
}
export async function obterVaga(id: number): Promise<VagaResposta> {
  const { data } = await api.get<VagaResposta>(`/vagas/${id}`)
  return data
}
export async function criarVaga(titulo: string, descricao: string): Promise<VagaResposta> {
  const { data } = await api.post<VagaResposta>('/vagas', { titulo, descricao })
  return data
}
/**
 * Salva a régua da vaga. Se já houver candidatos avaliados, o backend reprocessa
 * (determinístico ou reextração com IA) e devolve `reprocesso` para o feedback.
 * Use `reprocessar=false` apenas para salvar sem disparar o reprocesso.
 */
export async function salvarRegua(
  id: number,
  regua: Regua,
  reprocessar = true,
): Promise<VagaResposta> {
  const { data } = await api.put<VagaResposta>(`/vagas/${id}`, regua, {
    params: { reprocessar },
  })
  return data
}
export async function rankingVaga(id: number): Promise<RankingVaga> {
  const { data } = await api.get<RankingVaga>(`/vagas/${id}/ranking`)
  return data
}
export async function reprocessarFalhas(
  vagaId: number,
): Promise<{ reenfileirados: number; lote_id: number | null }> {
  const { data } = await api.post(`/vagas/${vagaId}/reprocessar-falhas`)
  return data
}
/** Arquiva a vaga (sai da lista de ativas; nada é apagado). */
export async function arquivarVaga(id: number): Promise<VagaResumo> {
  const { data } = await api.post<VagaResumo>(`/vagas/${id}/arquivar`)
  return data
}
/** Restaura uma vaga arquivada de volta para ativa. */
export async function restaurarVaga(id: number): Promise<VagaResumo> {
  const { data } = await api.post<VagaResumo>(`/vagas/${id}/restaurar`)
  return data
}

// --- Lotes ---
export async function criarLote(vagaId: number, arquivos: File[]): Promise<LoteCriado> {
  const form = new FormData()
  arquivos.forEach((a) => form.append('arquivos', a))
  const { data } = await api.post<LoteCriado>(`/vagas/${vagaId}/lotes`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}
export async function statusLote(id: number): Promise<StatusLoteResposta> {
  const { data } = await api.get<StatusLoteResposta>(`/lotes/${id}`)
  return data
}

// --- Avaliações ---
export async function obterFicha(candidatoId: number): Promise<FichaCandidato> {
  const { data } = await api.get<FichaCandidato>(`/avaliacoes/${candidatoId}`)
  return data
}

/** URL do currículo original (PDF/TXT) para abrir no modal (iframe/visualizador). */
export function urlCv(candidatoId: number): string {
  return `/api/avaliacoes/${candidatoId}/cv`
}

// --- Notificações ---
export async function listarNotificacoes(): Promise<Notificacao[]> {
  const { data } = await api.get<Notificacao[]>('/notificacoes')
  return data
}
export async function marcarLida(id: number): Promise<void> {
  await api.put(`/notificacoes/${id}/lida`)
}

// --- Métricas ---
export async function obterMetricas(): Promise<MetricasOperacionais> {
  const { data } = await api.get<MetricasOperacionais>('/metricas')
  return data
}

// --- Configuração (low-code) ---
export async function obterConfiguracao(): Promise<ConfiguracaoSnapshot> {
  const { data } = await api.get<ConfiguracaoSnapshot>('/configuracao')
  return data
}
export async function salvarConfiguracao(
  parcial: Record<string, unknown>,
): Promise<ConfiguracaoSnapshot> {
  const { data } = await api.put<ConfiguracaoSnapshot>('/configuracao', parcial)
  return data
}
export async function testarChave(
  provedor: 'anthropic' | 'openai' | 'gemini',
  apiKey?: string,
): Promise<TesteChave> {
  const { data } = await api.post<TesteChave>('/configuracao/testar-chave', {
    provedor,
    api_key: apiKey,
  })
  return data
}
export async function removerChave(
  slot: 'principal' | 'secundaria',
): Promise<ConfiguracaoSnapshot> {
  const { data } = await api.delete<ConfiguracaoSnapshot>(`/configuracao/provedor/${slot}`)
  return data
}

/** Extrai uma mensagem de erro legível de uma exceção do axios. */
export function mensagemErro(erro: unknown): string {
  if (axios.isAxiosError(erro)) {
    const detalhe = erro.response?.data?.detail
    if (typeof detalhe === 'string') return detalhe
    return erro.message
  }
  return 'Erro inesperado.'
}
