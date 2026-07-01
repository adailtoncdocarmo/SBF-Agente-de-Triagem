import { BarChart3, Settings, UserSearch, type LucideIcon } from 'lucide-react'

/** Metadados de uma rota/menu — compartilhados entre Sidebar e Topbar. */
export interface ItemNav {
  path: string
  label: string
  icon: LucideIcon
  /** Texto auxiliar do cabeçalho da página. */
  subtitulo: string
  /** Distintivo opcional (ex.: contagem) — usado na Fase 2. */
  badge?: string
}

/** Rótulo da seção de navegação. */
export const SECAO_NAV = 'Triagem Inteligente'

// Dois menus, simples: Métricas (o diferencial, primeira tela) e Triagem (onde
// se cadastra a vaga, sobem-se currículos e vê-se o ranking dos candidatos).
export const ITENS_NAV: ItemNav[] = [
  {
    path: '/',
    label: 'Métricas',
    icon: BarChart3,
    subtitulo: 'Throughput, distribuição de zonas, latência e custo da triagem.',
  },
  {
    path: '/vagas',
    label: 'Triagem',
    icon: UserSearch,
    subtitulo: 'Cadastre a vaga, suba os currículos e veja o ranking dos candidatos.',
  },
]

/** Item de navegação de Configurações (renderizado na base da sidebar). */
export const CONFIG_NAV: ItemNav = {
  path: '/configuracoes',
  label: 'Configurações',
  icon: Settings,
  subtitulo: 'Chave de API, modelos, skills e fallback: tudo editável sem mexer no código.',
}

/** Encontra o item de navegação correspondente ao caminho atual (com sub-rotas). */
export function itemPorPath(pathname: string): ItemNav {
  const exato = ITENS_NAV.find((i) => i.path === pathname)
  if (exato) return exato
  if (pathname.startsWith('/configuracoes')) return CONFIG_NAV
  // Sub-rotas da Triagem (vaga/lote/candidato) acendem o menu Triagem.
  if (
    pathname.startsWith('/vagas') ||
    pathname.startsWith('/triagem') ||
    pathname.startsWith('/candidatos')
  ) {
    return ITENS_NAV.find((i) => i.path === '/vagas') ?? ITENS_NAV[0]
  }
  // Tudo o mais (inclusive '/') cai em Métricas, a tela inicial.
  return ITENS_NAV.find((i) => i.path === '/') ?? ITENS_NAV[0]
}
