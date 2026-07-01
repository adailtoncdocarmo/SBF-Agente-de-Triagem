import type { ReactNode } from 'react'

interface PageHeaderProps {
  titulo: string
  subtitulo: string
  acoes?: ReactNode
}

/** Cabeçalho padrão das páginas: título + subtítulo + ações opcionais. */
export default function PageHeader({ titulo, subtitulo, acoes }: PageHeaderProps) {
  return (
    <div className="page-header">
      <div>
        <h1 className="page-title">{titulo}</h1>
        <p className="page-subtitle">{subtitulo}</p>
      </div>
      {acoes && <div className="page-actions">{acoes}</div>}
    </div>
  )
}
