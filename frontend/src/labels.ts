// Mapeamentos de rótulos e classes de badge para os vocabulários do domínio.

import type { Confianca, EstadoKnockout, Recomendacao, StatusCritico, Thresholds, ZonaDecisao } from './types'

/**
 * Preset de rigor da seleção (corte do "verde"/auto-shortlist) por vaga.
 * Em vez de expor percentil/piso crus (abstratos), o RH escolhe um nível e o
 * sistema aplica os cortes por trás. Mais exigente → menos gente no verde.
 */
export type RigorPreset = 'flexivel' | 'equilibrado' | 'rigoroso'
export const PRESETS_RIGOR: Record<
  RigorPreset,
  { label: string; corte_verde: number; corte_amarelo: number; dica: string }
> = {
  flexivel: { label: 'Flexível', corte_verde: 45, corte_amarelo: 25, dica: 'Verde a partir de 45 pontos: mais candidatos no verde, bom para alto volume.' },
  equilibrado: { label: 'Equilibrado', corte_verde: 60, corte_amarelo: 35, dica: 'Verde a partir de 60 pontos: equilíbrio entre seletividade e cobertura.' },
  rigoroso: { label: 'Rigoroso', corte_verde: 75, corte_amarelo: 50, dica: 'Verde a partir de 75 pontos: só os melhores, bom para vagas críticas.' },
}

/** Infere o preset atual a partir do corte de verde salvo na régua. */
export function presetDeThresholds(th: Thresholds): RigorPreset {
  if (th.corte_verde <= 52) return 'flexivel'
  if (th.corte_verde <= 67) return 'equilibrado'
  return 'rigoroso'
}

export const RECO_BADGE: Record<Recomendacao, { label: string; classe: string }> = {
  avancar: { label: 'Promissor', classe: 'success' },
  avaliar: { label: 'Revisar', classe: 'warning' },
  nao_avancar: { label: 'Fora do perfil', classe: 'danger' },
}

export function recoBadge(r: Recomendacao | null): { label: string; classe: string } {
  return r ? RECO_BADGE[r] : { label: '—', classe: 'neutral' }
}

/** Verbo da recomendação no vocabulário do desafio (avançar/avaliar/não avançar). */
export const RECO_VERBO: Record<Recomendacao, string> = {
  avancar: 'Avançar',
  avaliar: 'Avaliar',
  nao_avancar: 'Não avançar',
}
export function recoVerbo(r: Recomendacao | null): string {
  return r ? RECO_VERBO[r] : '—'
}

/** Rótulos e cor (classe de zona) dos três grupos — usado nos chips e cards. */
export const ZONA_INFO: Record<ZonaDecisao, { label: string; classe: string }> = {
  entra: { label: 'Promissores', classe: 'entra' },
  avaliar: { label: 'Revisar', classe: 'avaliar' },
  cai: { label: 'Fora do perfil', classe: 'cai' },
}

export const CONFIANCA_LABEL: Record<Confianca, string> = {
  alta: 'Alta',
  media: 'Média',
  baixa: 'Baixa',
}

export const CONFIANCA_BADGE: Record<Confianca, string> = {
  alta: 'success',
  media: 'warning',
  baixa: 'danger',
}

export const ESTADO_KO_LABEL: Record<EstadoKnockout, string> = {
  atende: 'Atende',
  nao_atende: 'Não atende',
  nao_evidenciado: 'Não evidenciado',
}

export const ESTADO_KO_BADGE: Record<EstadoKnockout, string> = {
  atende: 'success',
  nao_atende: 'danger',
  nao_evidenciado: 'neutral',
}

export const STATUS_CRITICO_LABEL: Record<StatusCritico, string> = {
  aprovado: 'Atende',
  reprovado: 'Abaixo do exigido',
  validacao: 'Revisar',
  nao_aplicavel: '—',
}

/**
 * Nomes amigáveis das fases na tabela de custo das Métricas. Rótulos
 * orientados à AÇÃO (o que aquele estágio faz) para um leitor não-técnico
 * entender exatamente onde o custo de IA é gasto.
 */
export const ESTAGIO_LABEL: Record<string, string> = {
  regua: 'Avaliar a vaga',
  portao1: 'Conferir requisitos obrigatórios',
  scoring: 'Responder os critérios',
  flags: 'Detectar pontos de atenção',
  comparacao: 'Desempatar candidatos próximos',
  sintese: 'Criar a recomendação',
}
export function estagioLabel(id: string): string {
  return ESTAGIO_LABEL[id] ?? id
}

/** Descrição de uma linha para o leitor entender o que cada custo representa. */
export const ESTAGIO_DESC: Record<string, string> = {
  regua: 'A IA lê a descrição da vaga e propõe os critérios de avaliação.',
  portao1: 'Verifica se o candidato atende aos requisitos eliminatórios.',
  scoring: 'Dá uma nota de 0 a 4 para cada critério, com evidência do CV.',
  flags: 'Aponta riscos e lacunas (ex.: dados a confirmar na entrevista).',
  comparacao: 'Compara, dois a dois, candidatos com pontuação parecida.',
  sintese: 'Escreve a recomendação final e a justificativa de aderência.',
}
export function estagioDesc(id: string): string {
  return ESTAGIO_DESC[id] ?? ''
}

/** Formata um valor já em Reais como "R$ X,XX" (pt-BR). */
export function brl(valor: number | null | undefined, casas = 2): string {
  if (valor === null || valor === undefined) return '—'
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
    minimumFractionDigits: casas,
    maximumFractionDigits: casas,
  }).format(valor)
}

/** Data/hora precisa de uma notificação (ex.: "28 de jun., 14:32"). */
export function dataHora(iso?: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleString('pt-BR', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/** Tempo relativo curto ("agora", "há 5 min", "ontem") para o sino. */
export function tempoRelativo(iso?: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const segundos = (Date.now() - d.getTime()) / 1000
  if (segundos < 60) return 'agora'
  if (segundos < 3600) return `há ${Math.floor(segundos / 60)} min`
  if (segundos < 86_400) return `há ${Math.floor(segundos / 3600)} h`
  if (segundos < 172_800) return 'ontem'
  return dataHora(iso)
}

export const STATUS_CRITICO_BADGE: Record<StatusCritico, string> = {
  aprovado: 'success',
  reprovado: 'danger',
  validacao: 'warning',
  nao_aplicavel: 'neutral',
}

/** Traduz o peso (0–100) de um critério num nível qualitativo para a UI. */
export function nivelDePeso(peso: number): { label: string; classe: string } {
  if (peso >= 20) return { label: 'alto', classe: 'alto' }
  if (peso >= 10) return { label: 'médio', classe: 'medio' }
  return { label: 'baixo', classe: 'baixo' }
}

/** Formata uma taxa 0..1 como porcentagem inteira. */
export function pct(valor: number | null | undefined): string {
  if (valor === null || valor === undefined) return '—'
  return `${Math.round(valor * 100)}%`
}

/**
 * Nome de exibição do candidato. Usa o nome detectado no CV (capturado no
 * cegamento); se não houver, deriva um nome legível do arquivo (tira extensão,
 * prefixo "CV", tokens de versão e hashes). Último recurso: o id anônimo.
 */
export function nomeExibicao(c: {
  nome_candidato: string | null
  nome_arquivo: string
  id_anonimo: string
}): string {
  if (c.nome_candidato && c.nome_candidato.trim()) return c.nome_candidato.trim()
  let s = c.nome_arquivo
    .replace(/\.[^.]+$/, '') // extensão
    .replace(/[_]+/g, ' ') // _ → espaço
    .replace(/^\s*(cv|curr[ií]culo|resume)\s*-?\s*/i, '') // prefixo CV/Currículo
  s = s
    .split(/\s+/)
    .filter(
      (t) =>
        !/\d/.test(t) && // qualquer token com dígito (hash, código, versão) — nomes não têm
        !/^[A-Za-zÀ-ÿ]{14,}$/.test(t), // token muito longo sem dígito (hash puro)
    )
    .join(' ')
    .replace(/\s*-\s*$/, '')
    .replace(/^\s*-\s*/, '')
    .replace(/\s+/g, ' ')
    .trim()
  return s || c.id_anonimo
}
