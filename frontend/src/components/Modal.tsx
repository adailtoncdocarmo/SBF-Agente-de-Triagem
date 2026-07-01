import type { ReactNode } from 'react'
import { X } from 'lucide-react'

interface ModalProps {
  titulo: string
  aberto: boolean
  onFechar: () => void
  children: ReactNode
  /** `amplo` usa um card largo/alto — ideal para visualizar um PDF. */
  amplo?: boolean
  /** `medio` usa uma largura intermediária (~660px) — ideal para conteúdo de leitura. */
  medio?: boolean
}

/**
 * Modal simples reutilizável (overlay + card). Fecha ao clicar fora ou no X.
 * Reaproveita as classes `.modal-overlay`/`.modal-card` do design system.
 */
export default function Modal({
  titulo,
  aberto,
  onFechar,
  children,
  amplo = false,
  medio = false,
}: ModalProps) {
  if (!aberto) return null
  const variante = amplo ? 'modal-card-amplo' : medio ? 'modal-card-medio' : ''
  return (
    <div className="modal-overlay" onClick={onFechar}>
      <div
        className={`modal-card elevation-3 ${variante}`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-topo">
          <span className="modal-titulo">{titulo}</span>
          <button type="button" className="req-chip-x" onClick={onFechar} aria-label="Fechar">
            <X size={16} />
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}
