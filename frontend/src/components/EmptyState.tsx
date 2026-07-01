import type { LucideIcon } from 'lucide-react'
import { Sparkles } from 'lucide-react'

interface EmptyStateProps {
  icon: LucideIcon
  titulo: string
  descricao: string
  /** Texto da "pílula" de status (default: "Chega na Fase 2"). */
  pill?: string
}

/** Estado vazio reutilizável das telas em branco da Fase 1. */
export default function EmptyState({
  icon: Icone,
  titulo,
  descricao,
  pill = 'Chega na Fase 2',
}: EmptyStateProps) {
  return (
    <div className="empty-state elevation-2">
      <div className="empty-icon">
        <Icone strokeWidth={1.6} />
      </div>
      <div className="empty-title">{titulo}</div>
      <p className="empty-desc">{descricao}</p>
      <span className="empty-pill">
        <Sparkles size={14} />
        {pill}
      </span>
    </div>
  )
}
