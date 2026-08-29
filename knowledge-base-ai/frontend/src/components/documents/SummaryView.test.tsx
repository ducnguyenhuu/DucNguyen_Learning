/**
 * SummaryView component tests (T061)
 *
 * Strategy: mock generateSummary and getSummary from the API service;
 * verify rendering, loading states, and user interactions.
 */
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock('../../services/api', () => ({
  generateSummary: vi.fn(),
  getSummary: vi.fn(),
}));

import { generateSummary, getSummary } from '../../services/api';
import SummaryView from './SummaryView';

// ---------------------------------------------------------------------------
// Factories
// ---------------------------------------------------------------------------

const makeSummary = (overrides = {}) => ({
  id: 'sum-1',
  document_id: 'doc-1',
  summary_text: 'This is the test summary content.',
  section_references: [
    { section: 'Page 1', page: 1, contribution: 'Introduction content' },
    { section: 'Page 5', page: 5, contribution: 'Details section' },
  ],
  model_version: 'phi3.5',
  created_at: '2026-03-05T12:00:00Z',
  ...overrides,
});

function renderView(props: { documentId?: string; hasSummary?: boolean; onSummaryGenerated?: () => void } = {}) {
  return render(
    <SummaryView
      documentId={props.documentId ?? 'doc-1'}
      hasSummary={props.hasSummary ?? false}
      onSummaryGenerated={props.onSummaryGenerated}
    />,
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('SummaryView — no summary state', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows empty state when hasSummary=false', async () => {
    renderView({ hasSummary: false });
    expect(await screen.findByTestId('summary-empty')).toBeInTheDocument();
    expect(screen.getByText(/no summary generated yet/i)).toBeInTheDocument();
  });

  it('renders Generate Summary button when hasSummary=false', () => {
    renderView({ hasSummary: false });
    expect(screen.getByTestId('btn-generate')).toBeInTheDocument();
  });

  it('does not call getSummary on mount when hasSummary=false', () => {
    renderView({ hasSummary: false });
    expect(getSummary).not.toHaveBeenCalled();
  });
});

describe('SummaryView — fetch cached summary', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('calls getSummary on mount when hasSummary=true', async () => {
    vi.mocked(getSummary).mockResolvedValue(makeSummary());
    renderView({ hasSummary: true });
    await waitFor(() => expect(getSummary).toHaveBeenCalledWith('doc-1'));
  });

  it('shows loading state while fetching', () => {
    vi.mocked(getSummary).mockReturnValue(new Promise(() => {})); // never resolves
    renderView({ hasSummary: true });
    expect(screen.getByTestId('summary-loading')).toBeInTheDocument();
  });

  it('renders summary text after fetch', async () => {
    vi.mocked(getSummary).mockResolvedValue(makeSummary());
    renderView({ hasSummary: true });
    expect(await screen.findByTestId('summary-text')).toHaveTextContent(
      'This is the test summary content.',
    );
  });

  it('renders section references after fetch', async () => {
    vi.mocked(getSummary).mockResolvedValue(makeSummary());
    renderView({ hasSummary: true });
    await screen.findByTestId('section-references');
    const items = screen.getAllByTestId('section-reference-item');
    expect(items).toHaveLength(2);
    expect(items[0]).toHaveTextContent('Page 1');
    expect(items[0]).toHaveTextContent('p. 1');
  });

  it('handles null section_references gracefully', async () => {
    vi.mocked(getSummary).mockResolvedValue(makeSummary({ section_references: null }));
    renderView({ hasSummary: true });
    await screen.findByTestId('summary-view');
    expect(screen.queryByTestId('section-references')).not.toBeInTheDocument();
  });

  it('shows Regenerate button when summary exists', async () => {
    vi.mocked(getSummary).mockResolvedValue(makeSummary());
    renderView({ hasSummary: true });
    expect(await screen.findByTestId('btn-regenerate')).toBeInTheDocument();
  });

  it('shows error alert when getSummary fails', async () => {
    vi.mocked(getSummary).mockRejectedValue(new Error('Network failure'));
    renderView({ hasSummary: true });
    const alert = await screen.findByRole('alert');
    expect(alert).toBeInTheDocument();
  });
});

describe('SummaryView — generate summary', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('calls generateSummary when Generate button is clicked', async () => {
    vi.mocked(generateSummary).mockResolvedValue(makeSummary());
    renderView({ hasSummary: false });
    await userEvent.click(screen.getByTestId('btn-generate'));
    expect(generateSummary).toHaveBeenCalledWith('doc-1');
  });

  it('shows loading state while generating', async () => {
    let resolve!: (v: ReturnType<typeof makeSummary>) => void;
    vi.mocked(generateSummary).mockReturnValue(new Promise((r) => { resolve = r; }));
    renderView({ hasSummary: false });
    // Click generate button - should show loading
    await userEvent.click(screen.getByTestId('btn-generate'));
    expect(screen.getByTestId('summary-loading')).toBeInTheDocument();
    resolve(makeSummary());
  });

  it('shows summary after generation completes', async () => {
    vi.mocked(generateSummary).mockResolvedValue(makeSummary());
    renderView({ hasSummary: false });
    await userEvent.click(screen.getByTestId('btn-generate'));
    expect(await screen.findByTestId('summary-text')).toHaveTextContent(
      'This is the test summary content.',
    );
  });

  it('calls onSummaryGenerated callback after generation', async () => {
    const onGenerated = vi.fn();
    vi.mocked(generateSummary).mockResolvedValue(makeSummary());
    renderView({ hasSummary: false, onSummaryGenerated: onGenerated });
    await userEvent.click(screen.getByTestId('btn-generate'));
    await waitFor(() => expect(onGenerated).toHaveBeenCalledOnce());
  });

  it('hides Generate button and shows loading while generating', async () => {
    vi.mocked(generateSummary).mockReturnValue(new Promise(() => {}));
    renderView({ hasSummary: false });
    await userEvent.click(screen.getByTestId('btn-generate'));
    // The component replaces summary-empty with the loading state
    expect(screen.queryByTestId('btn-generate')).not.toBeInTheDocument();
    expect(screen.getByTestId('summary-loading')).toBeInTheDocument();
  });

  it('shows error alert when generateSummary fails', async () => {
    vi.mocked(generateSummary).mockRejectedValue(new Error('LLM unavailable'));
    renderView({ hasSummary: false });
    await userEvent.click(screen.getByTestId('btn-generate'));
    const alert = await screen.findByRole('alert');
    expect(alert).toBeInTheDocument();
    expect(alert).toHaveTextContent('LLM unavailable');
  });
});

describe('SummaryView — regenerate', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getSummary).mockResolvedValue(makeSummary());
  });

  it('calls generateSummary when Regenerate button is clicked', async () => {
    vi.mocked(generateSummary).mockResolvedValue(makeSummary({ summary_text: 'Updated summary' }));
    renderView({ hasSummary: true });
    const btn = await screen.findByTestId('btn-regenerate');
    await userEvent.click(btn);
    expect(generateSummary).toHaveBeenCalledWith('doc-1');
  });

  it('updates summary text after regeneration', async () => {
    vi.mocked(generateSummary).mockResolvedValue(makeSummary({ summary_text: 'Updated summary' }));
    renderView({ hasSummary: true });
    const btn = await screen.findByTestId('btn-regenerate');
    await userEvent.click(btn);
    expect(await screen.findByText('Updated summary')).toBeInTheDocument();
  });
});
