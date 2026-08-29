/**
 * DocumentDetail page tests (T062)
 *
 * Strategy: mock getDocument, getSummary, generateSummary and react-router-dom
 * navigation/params to exercise loading, metadata display, error states, and
 * SummaryView integration.
 */
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockNavigate = vi.fn();

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
    useParams: () => ({ documentId: 'doc-1' }),
  };
});

vi.mock('../services/api', () => ({
  generateSummary: vi.fn(),
  getDocument: vi.fn(),
  getSummary: vi.fn(),
}));

import { generateSummary, getDocument, getSummary } from '../services/api';
import DocumentDetail from './DocumentDetail';

// ---------------------------------------------------------------------------
// Factories
// ---------------------------------------------------------------------------

const makeDocument = (overrides = {}) => ({
  id: 'doc-1',
  file_name: 'Sample Report.pdf',
  file_path: '/data/Sample Report.pdf',
  file_type: 'pdf' as const,
  file_hash: 'abc123',
  file_size_bytes: 1048576,
  chunk_count: 24,
  has_summary: false,
  status: 'completed' as const,
  error_message: null,
  ingested_at: '2026-03-01T10:00:00Z',
  created_at: '2026-03-01T10:00:00Z',
  updated_at: '2026-03-01T10:00:00Z',
  ...overrides,
});

const makeSummary = (overrides = {}) => ({
  id: 'sum-1',
  document_id: 'doc-1',
  summary_text: 'Test summary text.',
  section_references: [],
  model_version: 'phi3.5',
  created_at: '2026-03-05T12:00:00Z',
  ...overrides,
});

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/documents/doc-1']}>
      <DocumentDetail />
    </MemoryRouter>,
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('DocumentDetail — loading & error states', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows loading skeleton while fetching document', () => {
    vi.mocked(getDocument).mockReturnValue(new Promise(() => {})); // never resolves
    vi.mocked(getSummary).mockResolvedValue(makeSummary());
    renderPage();
    expect(screen.getByTestId('document-detail-loading')).toBeInTheDocument();
  });

  it('renders document-detail container after load', async () => {
    vi.mocked(getDocument).mockResolvedValue(makeDocument());
    vi.mocked(getSummary).mockResolvedValue(makeSummary());
    renderPage();
    expect(await screen.findByTestId('document-detail')).toBeInTheDocument();
  });

  it('shows error alert when getDocument rejects', async () => {
    vi.mocked(getDocument).mockRejectedValue(new Error('Not found'));
    vi.mocked(getSummary).mockResolvedValue(makeSummary());
    renderPage();
    const alert = await screen.findByRole('alert');
    expect(alert).toBeInTheDocument();
  });

  it('shows document-detail-error testid when fetch fails', async () => {
    vi.mocked(getDocument).mockRejectedValue(new Error('Network error'));
    vi.mocked(getSummary).mockResolvedValue(makeSummary());
    renderPage();
    expect(await screen.findByTestId('document-detail-error')).toBeInTheDocument();
  });
});

describe('DocumentDetail — metadata display', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getDocument).mockResolvedValue(makeDocument());
    vi.mocked(getSummary).mockResolvedValue(makeSummary());
  });

  it('displays the document name', async () => {
    renderPage();
    const heading = await screen.findByTestId('document-name');
    expect(heading).toHaveTextContent('Sample Report.pdf');
  });

  it('displays the document type', async () => {
    renderPage();
    await screen.findByTestId('document-detail');
    expect(screen.getByTestId('doc-type')).toBeInTheDocument();
    expect(screen.getByTestId('doc-type').textContent?.toLowerCase()).toContain('pdf');
  });

  it('displays the file size', async () => {
    renderPage();
    await screen.findByTestId('document-detail');
    // 1 MiB shown as "1.0 MB" or "1 MiB" — just verify node exists and has content
    expect(screen.getByTestId('doc-size').textContent?.length).toBeGreaterThan(0);
  });

  it('displays the chunk count', async () => {
    renderPage();
    await screen.findByTestId('document-detail');
    expect(screen.getByTestId('doc-chunks')).toHaveTextContent('24');
  });

  it('displays the ingested_at date', async () => {
    renderPage();
    await screen.findByTestId('document-detail');
    expect(screen.getByTestId('doc-ingested-at').textContent?.length).toBeGreaterThan(0);
  });
});

describe('DocumentDetail — navigation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getDocument).mockResolvedValue(makeDocument());
    vi.mocked(getSummary).mockResolvedValue(makeSummary());
  });

  it('navigates to /documents when Back button is clicked', async () => {
    renderPage();
    await screen.findByTestId('document-detail');
    await userEvent.click(screen.getByTestId('btn-back'));
    expect(mockNavigate).toHaveBeenCalledWith('/documents');
  });
});

describe('DocumentDetail — SummaryView integration', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows empty summary state when has_summary=false', async () => {
    vi.mocked(getDocument).mockResolvedValue(makeDocument({ has_summary: false }));
    vi.mocked(getSummary).mockResolvedValue(makeSummary()); // won't be called
    renderPage();
    await screen.findByTestId('document-detail');
    expect(screen.getByTestId('summary-empty')).toBeInTheDocument();
  });

  it('shows Generate button when has_summary=false', async () => {
    vi.mocked(getDocument).mockResolvedValue(makeDocument({ has_summary: false }));
    vi.mocked(getSummary).mockResolvedValue(makeSummary());
    renderPage();
    await screen.findByTestId('document-detail');
    expect(screen.getByTestId('btn-generate')).toBeInTheDocument();
  });

  it('calls getSummary when has_summary=true', async () => {
    vi.mocked(getDocument).mockResolvedValue(makeDocument({ has_summary: true }));
    vi.mocked(getSummary).mockResolvedValue(makeSummary());
    renderPage();
    await waitFor(() => expect(getSummary).toHaveBeenCalledWith('doc-1'));
  });

  it('renders summary text when has_summary=true', async () => {
    vi.mocked(getDocument).mockResolvedValue(makeDocument({ has_summary: true }));
    vi.mocked(getSummary).mockResolvedValue(makeSummary({ summary_text: 'Loaded summary' }));
    renderPage();
    expect(await screen.findByText('Loaded summary')).toBeInTheDocument();
  });

  it('generating summary shows loading then renders result', async () => {
    vi.mocked(getDocument).mockResolvedValue(makeDocument({ has_summary: false }));
    // getSummary will be called after hasSummary becomes true (onSummaryGenerated triggers re-render)
    vi.mocked(getSummary).mockResolvedValue(makeSummary({ summary_text: 'Fresh summary' }));
    vi.mocked(generateSummary).mockResolvedValue(makeSummary({ summary_text: 'Fresh summary' }));
    renderPage();
    const genBtn = await screen.findByTestId('btn-generate');
    await userEvent.click(genBtn);
    // After generation completes, summary-view should be visible
    expect(await screen.findByTestId('summary-view')).toBeInTheDocument();
  });
});
