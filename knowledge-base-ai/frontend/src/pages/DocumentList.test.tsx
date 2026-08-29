/**
 * DocumentList page tests — T044
 *
 * Strategy: mock both hooks (useDocuments, useIngestion) and child components
 * (DocumentTable, IngestionProgress, LoadingSpinner). Tests validate page-level
 * orchestration: conditional rendering, button behaviour, auto-refresh, navigation.
 */

import { render, screen, fireEvent, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import DocumentList from './DocumentList';

// ---------------------------------------------------------------------------
// Hoisted helpers — must run before vi.mock factories
// ---------------------------------------------------------------------------

const {
  mockUseDocuments,
  mockUseIngestion,
  mockNavigate,
  mockDocuments,
  mockJob,
} = vi.hoisted(() => {
  const mockNavigate = vi.fn();

  // A minimal document fixture
  const mockDocuments = [
    {
      id: 'doc-1',
      file_name: 'arch.pdf',
      file_path: '/docs/arch.pdf',
      file_type: 'pdf',
      file_hash: 'abc',
      file_size_bytes: 1024,
      chunk_count: 42,
      status: 'completed',
      error_message: null,
      ingested_at: '2024-01-01T00:00:00Z',
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
    },
  ];

  // A minimal IngestionJob fixture
  const mockJob = {
    id: 'job-1',
    status: 'running',
    source_folder: '/docs',
    total_files: 10,
    processed_files: 5,
    new_files: 3,
    modified_files: 1,
    deleted_files: 0,
    skipped_files: 1,
    progress_pct: 50,
    error_message: null,
    started_at: new Date().toISOString(),
    completed_at: null,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };

  // Default return values for the hooks
  const defaultDocuments = {
    documents: [] as typeof mockDocuments,
    total: 0,
    page: 1,
    pageSize: 50,
    loading: false,
    error: null as string | null,
    deleting: false,
    deleteError: null as string | null,
    deleteDocument: vi.fn(),
    refresh: vi.fn(),
  };

  const defaultIngestion = {
    job: null as typeof mockJob | null,
    currentFile: null as string | null,
    fileErrors: [] as string[],
    starting: false,
    startError: null as string | null,
    isRunning: false,
    reconnecting: false,
    startIngestion: vi.fn().mockResolvedValue(undefined),
    reset: vi.fn(),
  };

  const mockUseDocuments = vi.fn(() => ({ ...defaultDocuments }));
  const mockUseIngestion = vi.fn(() => ({ ...defaultIngestion }));

  return { mockUseDocuments, mockUseIngestion, mockNavigate, mockDocuments, mockJob };
});

// ---------------------------------------------------------------------------
// Module mocks
// ---------------------------------------------------------------------------

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

vi.mock('../hooks/useDocuments', () => ({
  useDocuments: mockUseDocuments,
}));

vi.mock('../hooks/useIngestion', () => ({
  useIngestion: mockUseIngestion,
}));

// Stub heavy child components — we test their integration separately
vi.mock('../components/documents/DocumentTable', () => ({
  default: ({
    documents,
    onDelete,
    onGenerateSummary,
  }: {
    documents: { id: string; file_name: string }[];
    onDelete: (id: string) => Promise<void>;
    onGenerateSummary: (id: string) => void;
  }) => (
    <div data-testid="document-table">
      {documents.map((d) => (
        <div key={d.id} data-testid={`doc-row-${d.id}`}>
          <span>{d.file_name}</span>
          <button
            data-testid={`delete-${d.id}`}
            onClick={() => { void onDelete(d.id); }}
          >
            Delete
          </button>
          <button
            data-testid={`summary-${d.id}`}
            onClick={() => onGenerateSummary(d.id)}
          >
            Summary
          </button>
        </div>
      ))}
    </div>
  ),
}));

vi.mock('../components/documents/IngestionProgress', () => ({
  default: ({ job }: { job: { id: string } }) => (
    <div data-testid="ingestion-progress" data-job-id={job.id} />
  ),
}));

vi.mock('../components/common/LoadingSpinner', () => ({
  default: () => <div data-testid="loading-spinner" />,
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderPage() {
  return render(
    <MemoryRouter>
      <DocumentList />
    </MemoryRouter>
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('DocumentList', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Reset to defaults
    mockUseDocuments.mockReturnValue({
      documents: [],
      total: 0,
      page: 1,
      pageSize: 50,
      loading: false,
      error: null,
      deleting: false,
      deleteError: null,
      deleteDocument: vi.fn().mockResolvedValue(undefined),
      refresh: vi.fn(),
    });
    mockUseIngestion.mockReturnValue({
      job: null,
      currentFile: null,
      fileErrors: [],
      starting: false,
      startError: null,
      isRunning: false,
      reconnecting: false,
      startIngestion: vi.fn().mockResolvedValue(undefined),
      reset: vi.fn(),
    });
  });

  // ── Layout ──────────────────────────────────────────────────────────────

  it('renders page heading', () => {
    renderPage();
    expect(screen.getByRole('heading', { name: 'Documents' })).toBeInTheDocument();
  });

  it('renders the Run Ingest button', () => {
    renderPage();
    // The button appears in both the header and the empty-state CTA
    const buttons = screen.getAllByRole('button', { name: /run ingest/i });
    expect(buttons.length).toBeGreaterThanOrEqual(1);
  });

  // ── Loading state ────────────────────────────────────────────────────────

  it('shows skeleton when loading and no documents', () => {
    mockUseDocuments.mockReturnValue({
      documents: [],
      total: 0,
      page: 1,
      pageSize: 50,
      loading: true,
      error: null,
      deleting: false,
      deleteError: null,
      deleteDocument: vi.fn(),
      refresh: vi.fn(),
    });
    renderPage();
    expect(screen.getByRole('status', { name: /loading documents/i })).toBeInTheDocument();
    expect(screen.queryByTestId('document-table')).not.toBeInTheDocument();
  });

  it('shows refreshing indicator when loading with existing documents', () => {
    mockUseDocuments.mockReturnValue({
      documents: mockDocuments,
      total: 1,
      page: 1,
      pageSize: 50,
      loading: true,
      error: null,
      deleting: false,
      deleteError: null,
      deleteDocument: vi.fn(),
      refresh: vi.fn(),
    });
    renderPage();
    expect(screen.getByTestId('loading-spinner')).toBeInTheDocument();
    expect(screen.getByText(/refreshing/i)).toBeInTheDocument();
    // Table is still visible with stale data during re-fetch
    expect(screen.getByTestId('document-table')).toBeInTheDocument();
    expect(screen.getByText('arch.pdf')).toBeInTheDocument();
  });

  // ── Empty state ──────────────────────────────────────────────────────────

  it('shows empty state when no documents and no active job', () => {
    renderPage();
    expect(screen.getByText('No documents yet')).toBeInTheDocument();
    expect(screen.getByText(/run ingest to get started/i)).toBeInTheDocument();
  });

  it('does not show empty state while loading', () => {
    mockUseDocuments.mockReturnValue({
      documents: [],
      total: 0,
      page: 1,
      pageSize: 50,
      loading: true,
      error: null,
      deleting: false,
      deleteError: null,
      deleteDocument: vi.fn(),
      refresh: vi.fn(),
    });
    renderPage();
    expect(screen.queryByText('No documents yet')).not.toBeInTheDocument();
  });

  it('does not show empty state when a job is active', () => {
    mockUseIngestion.mockReturnValue({
      job: mockJob,
      currentFile: 'file.pdf',
      fileErrors: [],
      starting: false,
      startError: null,
      isRunning: true,
      reconnecting: false,
      startIngestion: vi.fn(),
      reset: vi.fn(),
    });
    renderPage();
    expect(screen.queryByText('No documents yet')).not.toBeInTheDocument();
  });

  // ── Document table ───────────────────────────────────────────────────────

  it('renders DocumentTable with documents', () => {
    mockUseDocuments.mockReturnValue({
      documents: mockDocuments,
      total: 1,
      page: 1,
      pageSize: 50,
      loading: false,
      error: null,
      deleting: false,
      deleteError: null,
      deleteDocument: vi.fn(),
      refresh: vi.fn(),
    });
    renderPage();
    expect(screen.getByTestId('document-table')).toBeInTheDocument();
    expect(screen.getByText('arch.pdf')).toBeInTheDocument();
  });

  it('does not render DocumentTable when documents list is empty', () => {
    renderPage();
    expect(screen.queryByTestId('document-table')).not.toBeInTheDocument();
  });

  // ── Ingestion progress ───────────────────────────────────────────────────

  it('shows IngestionProgress when job is not null', () => {
    mockUseIngestion.mockReturnValue({
      job: mockJob,
      currentFile: 'current.pdf',
      fileErrors: [],
      starting: false,
      startError: null,
      isRunning: true,
      reconnecting: false,
      startIngestion: vi.fn(),
      reset: vi.fn(),
    });
    renderPage();
    const progress = screen.getByTestId('ingestion-progress');
    expect(progress).toBeInTheDocument();
    expect(progress).toHaveAttribute('data-job-id', 'job-1');
  });

  it('hides IngestionProgress when job is null', () => {
    renderPage();
    expect(screen.queryByTestId('ingestion-progress')).not.toBeInTheDocument();
  });

  // ── Run Ingest button ────────────────────────────────────────────────────

  it('calls startIngestion when Run Ingest is clicked', () => {
    const startIngestion = vi.fn().mockResolvedValue(undefined);
    mockUseIngestion.mockReturnValue({
      job: null,
      currentFile: null,
      fileErrors: [],
      starting: false,
      startError: null,
      isRunning: false,
      reconnecting: false,
      startIngestion,
      reset: vi.fn(),
    });
    renderPage();
    act(() => {
      // Click the header button (first occurrence)
      const [headerBtn] = screen.getAllByRole('button', { name: /run ingest/i });
      fireEvent.click(headerBtn);
    });
    expect(startIngestion).toHaveBeenCalledOnce();
  });

  it('shows "Ingesting…" and disables button while isRunning', () => {
    mockUseIngestion.mockReturnValue({
      job: mockJob,
      currentFile: null,
      fileErrors: [],
      starting: false,
      startError: null,
      isRunning: true,
      reconnecting: false,
      startIngestion: vi.fn(),
      reset: vi.fn(),
    });
    renderPage();
    const btn = screen.getAllByRole('button', { name: /ingesting/i })[0];
    expect(btn).toBeDisabled();
  });

  it('shows "Starting…" and disables button while starting', () => {
    mockUseIngestion.mockReturnValue({
      job: null,
      currentFile: null,
      fileErrors: [],
      starting: true,
      startError: null,
      isRunning: false,
      reconnecting: false,
      startIngestion: vi.fn(),
      reset: vi.fn(),
    });
    renderPage();
    const btn = screen.getAllByRole('button', { name: /starting/i })[0];
    expect(btn).toBeDisabled();
  });

  // ── Error banners ─────────────────────────────────────────────────────────

  it('shows startError alert when ingestion start fails', () => {
    mockUseIngestion.mockReturnValue({
      job: null,
      currentFile: null,
      fileErrors: [],
      starting: false,
      startError: 'An ingestion job is already in progress.',
      isRunning: false,
      reconnecting: false,
      startIngestion: vi.fn(),
      reset: vi.fn(),
    });
    renderPage();
    expect(
      screen.getByRole('alert')
    ).toHaveTextContent('An ingestion job is already in progress.');
  });

  it('shows fetchError alert when document list fetch fails', () => {
    mockUseDocuments.mockReturnValue({
      documents: [],
      total: 0,
      page: 1,
      pageSize: 50,
      loading: false,
      error: 'Failed to load documents.',
      deleting: false,
      deleteError: null,
      deleteDocument: vi.fn(),
      refresh: vi.fn(),
    });
    renderPage();
    expect(screen.getByRole('alert')).toHaveTextContent('Failed to load documents.');
  });

  // ── Auto-refresh after ingestion ─────────────────────────────────────────

  it('calls refresh() when job status becomes completed', () => {
    const refresh = vi.fn();
    mockUseDocuments.mockReturnValue({
      documents: [],
      total: 0,
      page: 1,
      pageSize: 50,
      loading: false,
      error: null,
      deleting: false,
      deleteError: null,
      deleteDocument: vi.fn(),
      refresh,
    });
    mockUseIngestion.mockReturnValue({
      job: { ...mockJob, status: 'completed' },
      currentFile: null,
      fileErrors: [],
      starting: false,
      startError: null,
      isRunning: false,
      reconnecting: false,
      startIngestion: vi.fn(),
      reset: vi.fn(),
    });
    renderPage();
    expect(refresh).toHaveBeenCalledOnce();
  });

  it('does not call refresh() when job status is running', () => {
    const refresh = vi.fn();
    mockUseDocuments.mockReturnValue({
      documents: [],
      total: 0,
      page: 1,
      pageSize: 50,
      loading: false,
      error: null,
      deleting: false,
      deleteError: null,
      deleteDocument: vi.fn(),
      refresh,
    });
    mockUseIngestion.mockReturnValue({
      job: { ...mockJob, status: 'running' },
      currentFile: null,
      fileErrors: [],
      starting: false,
      startError: null,
      isRunning: true,
      reconnecting: false,
      startIngestion: vi.fn(),
      reset: vi.fn(),
    });
    renderPage();
    expect(refresh).not.toHaveBeenCalled();
  });

  // ── Navigation ────────────────────────────────────────────────────────────

  it('navigates to document detail when Summary is clicked', () => {
    mockUseDocuments.mockReturnValue({
      documents: mockDocuments,
      total: 1,
      page: 1,
      pageSize: 50,
      loading: false,
      error: null,
      deleting: false,
      deleteError: null,
      deleteDocument: vi.fn(),
      refresh: vi.fn(),
    });
    renderPage();
    act(() => {
      fireEvent.click(screen.getByTestId('summary-doc-1'));
    });
    expect(mockNavigate).toHaveBeenCalledWith('/documents/doc-1');
  });
});
