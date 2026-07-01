interface ProgressoLoteProps {
  texto?: string
  /** Quando informados (>0), mostra barra determinada X/N + %. Senão, indeterminada. */
  concluidos?: number
  total?: number
}

/**
 * Estado de carregamento elegante e animado: spinner + barra de progresso.
 * Usado no processamento do lote (com contagem X/N) e em carregamentos genéricos
 * (barra indeterminada).
 */
export default function ProgressoLote({ texto = 'Processando…', concluidos, total }: ProgressoLoteProps) {
  const temContagem = typeof total === 'number' && total > 0
  const pct = temContagem ? Math.round(((concluidos ?? 0) / (total as number)) * 100) : 0
  return (
    <div className="card elevation-2">
      <div className="card-body loading-lote">
        <div className="loading-spinner" aria-hidden />
        <p className="loading-titulo">{texto}</p>
        {temContagem ? (
          <>
            <div className="loading-barra">
              <div className="loading-barra-fill" style={{ width: `${pct}%` }} />
            </div>
            <p className="loading-sub">
              {concluidos} de {total} · {pct}%
            </p>
          </>
        ) : (
          <div className="loading-barra">
            <div className="loading-barra-fill indeterminado" />
          </div>
        )}
      </div>
    </div>
  )
}
