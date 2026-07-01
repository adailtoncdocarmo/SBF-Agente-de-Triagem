import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import App from './App'
import Vagas from './pages/Vagas'
import Metricas from './pages/Metricas'
import ResultadoLote from './pages/ResultadoLote'
import Ficha from './pages/Ficha'
import Configuracoes from './pages/Configuracoes'

import './styles/tokens.css'
import './styles/base.css'
import './styles/components.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<App />}>
          <Route index element={<Metricas />} />
          <Route path="vagas" element={<Vagas />} />
          <Route path="triagem/:loteId" element={<ResultadoLote />} />
          <Route path="candidatos/:candidatoId" element={<Ficha />} />
          <Route path="configuracoes" element={<Configuracoes />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
)
