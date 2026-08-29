/**
 * Application layout — sidebar navigation + main content area.
 *
 * Responsive per frontend-contract.md §5 & §10:
 *  - Desktop  (≥1024px) : sidebar (14rem fixed) + content
 *  - Tablet  (768-1023px): sidebar collapses to 48px icon-only strip;
 *                          tapping the toggle expands it as a full-width overlay
 *  - Mobile   (<768px)  : sidebar hidden; fixed bottom tab bar replaces it
 *
 * Keyboard: Escape collapses the expanded sidebar (WCAG 2.1).
 */
import { useCallback, useEffect, useRef } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { useState } from 'react';
import Navbar from './Navbar';
import ReembedBanner from './ReembedBanner';

const NAV_ITEMS = [
  { to: '/', icon: '🏠', label: 'Dashboard', end: true },
  { to: '/documents', icon: '📄', label: 'Documents', end: false },
  { to: '/chat', icon: '💬', label: 'Chat', end: false },
  { to: '/settings', icon: '⚙', label: 'Settings', end: false },
] as const;

export default function Layout() {
  const [sidebarExpanded, setSidebarExpanded] = useState(false);
  const toggleRef = useRef<HTMLButtonElement>(null);

  const closeSidebar = useCallback(() => setSidebarExpanded(false), []);

  // Collapse on Escape key (WCAG 2.1 §2.1.2)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && sidebarExpanded) closeSidebar();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [sidebarExpanded, closeSidebar]);

  return (
    <div className="layout">
      <Navbar />
      <ReembedBanner />
      <div className="layout__body">
        {/* Backdrop — rendered into DOM only when expanded; CSS hides on non-tablet */}
        {sidebarExpanded && (
          <div
            className="sidebar-backdrop"
            aria-hidden="true"
            data-testid="sidebar-backdrop"
            onClick={closeSidebar}
          />
        )}

        <aside
          className={`layout__sidebar${sidebarExpanded ? ' layout__sidebar--expanded' : ''}`}
          aria-label="Main navigation sidebar"
          data-testid="layout-sidebar"
        >
          {/* Toggle button — CSS shows only on tablet */}
          <button
            ref={toggleRef}
            type="button"
            className="sidebar-toggle"
            aria-label={sidebarExpanded ? 'Collapse navigation' : 'Expand navigation'}
            aria-expanded={sidebarExpanded}
            aria-controls="sidebar-nav"
            onClick={() => setSidebarExpanded((v) => !v)}
            data-testid="sidebar-toggle"
          >
            <span aria-hidden="true">{sidebarExpanded ? '✕' : '☰'}</span>
          </button>

          <nav id="sidebar-nav" aria-label="Main navigation">
            <ul className="nav-list">
              {NAV_ITEMS.map(({ to, icon, label, end }) => (
                <li key={to}>
                  <NavLink
                    to={to}
                    end={end}
                    className={({ isActive }) =>
                      isActive ? 'nav-link nav-link--active' : 'nav-link'
                    }
                    onClick={closeSidebar}
                  >
                    <span className="nav-link__icon" aria-hidden="true">
                      {icon}
                    </span>
                    <span className="nav-link__text">{label}</span>
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>
        </aside>

        <main className="layout__content" id="main-content">
          <Outlet />
        </main>
      </div>

      {/* Mobile bottom tab bar — CSS shows only on mobile */}
      <nav className="mobile-tabs" aria-label="Mobile navigation" data-testid="mobile-tabs">
        {NAV_ITEMS.map(({ to, icon, label, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              isActive ? 'mobile-tab mobile-tab--active' : 'mobile-tab'
            }
          >
            <span className="mobile-tab__icon" aria-hidden="true">
              {icon}
            </span>
            <span className="mobile-tab__label">{label}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
