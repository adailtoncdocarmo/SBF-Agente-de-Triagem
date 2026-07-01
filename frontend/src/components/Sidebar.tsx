import { MoreVertical } from 'lucide-react'
import { NavLink, useLocation } from 'react-router-dom'

import logoSbf from '../assets/logo-sbf.svg'
import { CONFIG_NAV, ITENS_NAV, SECAO_NAV, itemPorPath } from '../nav'

/** Barra lateral fixa: marca Grupo SBF + navegação (jornada) + rodapé de usuário. */
export default function Sidebar() {
  // O menu ativo é decidido por `itemPorPath` (não pelo match exato do NavLink),
  // para que sub-rotas como /triagem/:lote e /candidatos/:id acendam "Triagem".
  const { pathname } = useLocation()
  const ativo = itemPorPath(pathname).path
  return (
    <aside className="sidebar elevation-3">
      <div className="sidebar-brand">
        <img className="brand-logo-img" src={logoSbf} alt="Grupo SBF" width={36} height={36} />
        <div>
          <div className="brand-name">Grupo SBF</div>
          <div className="brand-suffix">Recursos Humanos</div>
        </div>
      </div>

      <div>
        <div className="sidebar-section-label">{SECAO_NAV}</div>
        <nav className="sidebar-nav">
          {ITENS_NAV.map((item) => {
            const Icone = item.icon
            return (
              <NavLink
                key={item.path}
                to={item.path}
                className={`nav-item${ativo === item.path ? ' active' : ''}`}
              >
                <Icone strokeWidth={1.8} />
                {item.label}
                {item.badge && <span className="nav-badge">{item.badge}</span>}
              </NavLink>
            )
          })}
        </nav>
      </div>

      <div className="sidebar-bottom">
        <NavLink
          to={CONFIG_NAV.path}
          className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
        >
          <CONFIG_NAV.icon strokeWidth={1.8} />
          {CONFIG_NAV.label}
        </NavLink>

        <div className="sidebar-footer">
          <div className="avatar">DC</div>
          <div className="user-info">
            <div className="user-name">Do Carmo</div>
            <div className="user-role">Product Builder</div>
          </div>
          <MoreVertical size={16} style={{ color: 'var(--text-tertiary)' }} />
        </div>
      </div>
    </aside>
  )
}
