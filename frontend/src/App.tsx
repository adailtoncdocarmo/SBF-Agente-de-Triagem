import { useEffect, useState } from 'react'
import { Outlet } from 'react-router-dom'

import Sidebar from './components/Sidebar'
import Topbar from './components/Topbar'

type Tema = 'light' | 'dark'

/**
 * Layout raiz: sidebar à esquerda + área principal (topbar + conteúdo da rota).
 * Gerencia o tema claro/escuro (padrão claro — marca SBF é white-forward).
 */
export default function App() {
  const [tema, setTema] = useState<Tema>('light')

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', tema)
  }, [tema])

  const alternarTema = () =>
    setTema((atual) => (atual === 'light' ? 'dark' : 'light'))

  return (
    <div className="app">
      <Sidebar />
      <main className="main">
        <Topbar tema={tema} onAlternarTema={alternarTema} />
        <div className="content">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
