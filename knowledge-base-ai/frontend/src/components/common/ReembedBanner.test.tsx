/**
 * Unit tests for ReembedBanner component.
 *
 * Covers:
 * - Hidden when reembedding=false
 * - Hidden while health is still loading (null)
 * - Shown when reembedding=true
 * - Banner contains "Re-embedding" text
 * - Banner contains a "View Progress" link to /documents
 * - Banner has role="alert" for accessibility
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ReembedBanner from './ReembedBanner';
import * as useHealthModule from '../../hooks/useHealth';
import type { UseHealthResult } from '../../hooks/useHealth';
import type { HealthResponse } from '../../services/types';

// ---------------------------------------------------------------------------
// Mock useHealth so the component never hits the network
// ---------------------------------------------------------------------------

vi.mock('../../hooks/useHealth', () => ({
  useHealth: vi.fn(),
}));

const mockUseHealth = vi.mocked(useHealthModule.useHealth);

function makeHealthResult(overrides: Partial<HealthResponse> = {}): UseHealthResult {
  return {
    health: {
      status: 'ok',
      database: 'ok',
      embedding_model: 'nomic-embed-text-v1.5',
      llm_model: 'phi3.5',
      ollama: 'ok',
      reembedding: false,
      ...overrides,
    },
    loading: false,
    error: null,
    refresh: vi.fn(),
  };
}

function renderBanner() {
  return render(
    <MemoryRouter>
      <ReembedBanner />
    </MemoryRouter>,
  );
}

describe('ReembedBanner', () => {
  beforeEach(() => {
    mockUseHealth.mockReset();
  });

  it('renders nothing when reembedding=false', () => {
    mockUseHealth.mockReturnValue(makeHealthResult({ reembedding: false }));
    const { container } = renderBanner();
    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing while health is null (loading)', () => {
    mockUseHealth.mockReturnValue({
      health: null,
      loading: true,
      error: null,
      refresh: vi.fn(),
    });
    const { container } = renderBanner();
    expect(container).toBeEmptyDOMElement();
  });

  it('renders banner when reembedding=true', () => {
    mockUseHealth.mockReturnValue(makeHealthResult({ reembedding: true }));
    renderBanner();
    expect(screen.getByTestId('reembed-banner')).toBeInTheDocument();
  });

  it('banner text mentions re-embedding', () => {
    mockUseHealth.mockReturnValue(makeHealthResult({ reembedding: true }));
    renderBanner();
    expect(screen.getByText(/re-embedding/i)).toBeInTheDocument();
  });

  it('banner contains a "View Progress" link', () => {
    mockUseHealth.mockReturnValue(makeHealthResult({ reembedding: true }));
    renderBanner();
    const link = screen.getByRole('link', { name: /view progress/i });
    expect(link).toBeInTheDocument();
  });

  it('"View Progress" link points to /documents', () => {
    mockUseHealth.mockReturnValue(makeHealthResult({ reembedding: true }));
    renderBanner();
    const link = screen.getByRole('link', { name: /view progress/i });
    expect(link).toHaveAttribute('href', '/documents');
  });

  it('banner has role="alert" for accessibility', () => {
    mockUseHealth.mockReturnValue(makeHealthResult({ reembedding: true }));
    renderBanner();
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });

  it('dismisses automatically when reembedding switches to false', () => {
    // First render: reembedding=true
    mockUseHealth.mockReturnValue(makeHealthResult({ reembedding: true }));
    const { rerender } = renderBanner();
    expect(screen.getByTestId('reembed-banner')).toBeInTheDocument();

    // Second render: reembedding=false (as if health poll returned false)
    mockUseHealth.mockReturnValue(makeHealthResult({ reembedding: false }));
    rerender(
      <MemoryRouter>
        <ReembedBanner />
      </MemoryRouter>,
    );
    expect(screen.queryByTestId('reembed-banner')).not.toBeInTheDocument();
  });
});
