/**
 * Unit tests for Layout component.
 *
 * Tests JS-controlled behaviour (sidebar toggle, Escape key, backdrop close).
 * Note: CSS-based breakpoint visibility cannot be tested in jsdom — those
 * are covered by visual/browser testing; here we test DOM structure and state.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import Layout from './Layout';

// Mock ReembedBanner's health polling so Layout renders cleanly
vi.mock('../../hooks/useHealth', () => ({
  useHealth: () => ({ health: null, loading: true, error: null, refresh: vi.fn() }),
}));

function renderLayout(initialPath = '/') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<div>Dashboard page</div>} />
          <Route path="documents" element={<div>Documents page</div>} />
          <Route path="chat" element={<div>Chat page</div>} />
          <Route path="settings" element={<div>Settings page</div>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

describe('Layout', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // ── Sidebar nav items ──────────────────────────────────────────────────
  it('renders all sidebar nav items', () => {
    renderLayout();
    const sidenav = screen.getByRole('navigation', { name: /main navigation$/i });
    expect(sidenav).toBeInTheDocument();
    expect(sidenav).toHaveTextContent('Dashboard');
    expect(sidenav).toHaveTextContent('Documents');
    expect(sidenav).toHaveTextContent('Chat');
    expect(sidenav).toHaveTextContent('Settings');
  });

  it('nav items are links', () => {
    renderLayout();
    // Sidebar contains links (multiple since mobile-tabs also has them)
    const dashLinks = screen.getAllByRole('link', { name: /dashboard/i });
    expect(dashLinks.length).toBeGreaterThanOrEqual(1);
  });

  it('renders outlet content', () => {
    renderLayout('/');
    expect(screen.getByText('Dashboard page')).toBeInTheDocument();
  });

  // ── Mobile tab bar ──────────────────────────────────────────────────────
  it('renders mobile navigation tab bar', () => {
    renderLayout();
    expect(screen.getByRole('navigation', { name: /mobile navigation/i })).toBeInTheDocument();
  });

  it('mobile tab bar contains all nav items', () => {
    renderLayout();
    const mobileNav = screen.getByTestId('mobile-tabs');
    expect(mobileNav).toHaveTextContent('Dashboard');
    expect(mobileNav).toHaveTextContent('Documents');
    expect(mobileNav).toHaveTextContent('Chat');
    expect(mobileNav).toHaveTextContent('Settings');
  });

  // ── Sidebar toggle ─────────────────────────────────────────────────────
  it('renders the sidebar toggle button', () => {
    renderLayout();
    expect(screen.getByTestId('sidebar-toggle')).toBeInTheDocument();
  });

  it('toggle button starts with aria-expanded="false"', () => {
    renderLayout();
    const toggle = screen.getByTestId('sidebar-toggle');
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
  });

  it('clicking toggle sets aria-expanded="true" and adds --expanded class', async () => {
    renderLayout();
    const toggle = screen.getByTestId('sidebar-toggle');
    await userEvent.click(toggle);

    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByTestId('layout-sidebar')).toHaveClass('layout__sidebar--expanded');
  });

  it('clicking toggle twice collapses sidebar again', async () => {
    renderLayout();
    const toggle = screen.getByTestId('sidebar-toggle');
    await userEvent.click(toggle);
    await userEvent.click(toggle);

    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    expect(screen.getByTestId('layout-sidebar')).not.toHaveClass('layout__sidebar--expanded');
  });

  it('toggle button label changes to "Collapse" when expanded', async () => {
    renderLayout();
    await userEvent.click(screen.getByTestId('sidebar-toggle'));
    expect(screen.getByRole('button', { name: /collapse navigation/i })).toBeInTheDocument();
  });

  // ── Backdrop ───────────────────────────────────────────────────────────
  it('backdrop is not rendered when sidebar is collapsed', () => {
    renderLayout();
    expect(screen.queryByTestId('sidebar-backdrop')).not.toBeInTheDocument();
  });

  it('backdrop is rendered when sidebar is expanded', async () => {
    renderLayout();
    await userEvent.click(screen.getByTestId('sidebar-toggle'));
    expect(screen.getByTestId('sidebar-backdrop')).toBeInTheDocument();
  });

  it('clicking backdrop collapses sidebar', async () => {
    renderLayout();
    await userEvent.click(screen.getByTestId('sidebar-toggle'));
    await userEvent.click(screen.getByTestId('sidebar-backdrop'));

    expect(screen.queryByTestId('sidebar-backdrop')).not.toBeInTheDocument();
    expect(screen.getByTestId('layout-sidebar')).not.toHaveClass('layout__sidebar--expanded');
  });

  // ── Escape key ─────────────────────────────────────────────────────────
  it('Escape key collapses expanded sidebar', async () => {
    renderLayout();
    await userEvent.click(screen.getByTestId('sidebar-toggle'));
    expect(screen.getByTestId('sidebar-backdrop')).toBeInTheDocument();

    await userEvent.keyboard('{Escape}');

    expect(screen.queryByTestId('sidebar-backdrop')).not.toBeInTheDocument();
    expect(screen.getByTestId('layout-sidebar')).not.toHaveClass('layout__sidebar--expanded');
  });

  it('Escape key has no effect when sidebar is already collapsed', async () => {
    renderLayout();
    // Sidebar starts collapsed — pressing Escape is harmless
    await userEvent.keyboard('{Escape}');
    expect(screen.queryByTestId('sidebar-backdrop')).not.toBeInTheDocument();
  });

  // ── Nav link click closes expanded sidebar ─────────────────────────────
  it('clicking a nav link closes the expanded sidebar', async () => {
    renderLayout('/');
    await userEvent.click(screen.getByTestId('sidebar-toggle'));
    expect(screen.getByTestId('sidebar-backdrop')).toBeInTheDocument();

    // Click the "Documents" nav link in the sidebar nav (not mobile tabs)
    const sidebarNav = screen.getByRole('navigation', { name: /main navigation$/i });
    const docsLink = sidebarNav.querySelector('a[href="/documents"]');
    expect(docsLink).not.toBeNull();
    await userEvent.click(docsLink!);

    expect(screen.queryByTestId('sidebar-backdrop')).not.toBeInTheDocument();
  });

  // ── Accessibility ──────────────────────────────────────────────────────
  it('sidebar has aria-label', () => {
    renderLayout();
    expect(screen.getByTestId('layout-sidebar')).toHaveAttribute('aria-label');
  });

  it('sidebar nav has aria-label', () => {
    renderLayout();
    expect(screen.getByRole('navigation', { name: /main navigation$/i })).toBeInTheDocument();
  });

  it('main content area has id="main-content"', () => {
    renderLayout();
    expect(document.getElementById('main-content')).toBeInTheDocument();
  });
});
