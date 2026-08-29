/**
 * Dashboard page tests (T058)
 *
 * Strategy: mock listDocuments, listConversations, getHealth from the API
 * service; verify stats cards, recent conversations, quick action navigation.
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
  return { ...actual, useNavigate: () => mockNavigate };
});

vi.mock('../services/api', () => ({
  listDocuments: vi.fn(),
  listConversations: vi.fn(),
  getHealth: vi.fn(),
}));

import { getHealth, listConversations, listDocuments } from '../services/api';
import Dashboard from './Dashboard';

// ---------------------------------------------------------------------------
// Factories
// ---------------------------------------------------------------------------

const makeDocsResponse = (total = 25) => ({
  documents: [],
  total,
  page: 1,
  page_size: 1,
});

const makeConvsResponse = (total = 5, count = 0) => ({
  conversations: Array.from({ length: count }, (_, i) => ({
    id: `conv-${i + 1}`,
    title: `Conversation ${i + 1}`,
    preview: 'Preview text',
    message_count: 3,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-02T00:00:00Z',
  })),
  total,
});

const makeHealthOk = () => ({
  status: 'ok' as const,
  database: 'ok' as const,
  embedding_model: 'nomic-embed-text-v1.5',
  llm_model: 'phi3.5',
  ollama: 'ok' as const,
  reembedding: false,
});

const makeHealthDegraded = () => ({
  ...makeHealthOk(),
  status: 'degraded' as const,
  ollama: 'unavailable' as const,
});

// ---------------------------------------------------------------------------
// Helper
// ---------------------------------------------------------------------------

function renderDashboard() {
  return render(
    <MemoryRouter>
      <Dashboard />
    </MemoryRouter>,
  );
}

function setupHappyPath(opts: { docTotal?: number; convTotal?: number; convCount?: number } = {}) {
  vi.mocked(listDocuments).mockResolvedValue(makeDocsResponse(opts.docTotal ?? 25));
  vi.mocked(listConversations).mockResolvedValue(
    makeConvsResponse(opts.convTotal ?? 5, opts.convCount ?? 3),
  );
  vi.mocked(getHealth).mockResolvedValue(makeHealthOk());
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('Dashboard — loading state', () => {
  it('shows loading indicator while fetching', () => {
    // Never resolves — stay in loading state
    vi.mocked(listDocuments).mockReturnValue(new Promise(() => {}));
    vi.mocked(listConversations).mockReturnValue(new Promise(() => {}));
    vi.mocked(getHealth).mockReturnValue(new Promise(() => {}));

    renderDashboard();
    expect(screen.getByTestId('dashboard-loading')).toBeInTheDocument();
  });
});

describe('Dashboard — error state', () => {
  it('shows error alert when any API call fails', async () => {
    vi.mocked(listDocuments).mockRejectedValue(new Error('Network error'));
    vi.mocked(listConversations).mockResolvedValue(makeConvsResponse());
    vi.mocked(getHealth).mockResolvedValue(makeHealthOk());

    renderDashboard();
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Network error');
  });

  it('does not show stats on error', async () => {
    vi.mocked(listDocuments).mockRejectedValue(new Error('oops'));
    vi.mocked(listConversations).mockResolvedValue(makeConvsResponse());
    vi.mocked(getHealth).mockResolvedValue(makeHealthOk());

    renderDashboard();
    await screen.findByRole('alert');
    expect(screen.queryByTestId('stat-docs')).not.toBeInTheDocument();
  });
});

describe('Dashboard — stats cards', () => {
  beforeEach(() => {
    mockNavigate.mockClear();
    setupHappyPath({ docTotal: 42, convTotal: 7, convCount: 0 });
  });

  it('renders the dashboard container', async () => {
    renderDashboard();
    expect(await screen.findByTestId('dashboard')).toBeInTheDocument();
  });

  it('shows document count stat card', async () => {
    renderDashboard();
    const card = await screen.findByTestId('stat-docs');
    expect(card).toBeInTheDocument();
    expect(card).toHaveTextContent('42');
  });

  it('shows conversation count stat card', async () => {
    renderDashboard();
    const card = await screen.findByTestId('stat-conversations');
    expect(card).toBeInTheDocument();
    expect(card).toHaveTextContent('7');
  });

  it('shows health stat card with OK status', async () => {
    renderDashboard();
    const card = await screen.findByTestId('stat-health');
    expect(card).toBeInTheDocument();
    expect(card).toHaveTextContent('OK');
  });

  it('shows degraded status when ollama is unavailable', async () => {
    vi.mocked(listDocuments).mockResolvedValue(makeDocsResponse());
    vi.mocked(listConversations).mockResolvedValue(makeConvsResponse(5, 0));
    vi.mocked(getHealth).mockResolvedValue(makeHealthDegraded());

    renderDashboard();
    const card = await screen.findByTestId('stat-health');
    expect(card).toHaveTextContent('Degraded');
  });
});

describe('Dashboard — recent conversations', () => {
  beforeEach(() => {
    mockNavigate.mockClear();
  });

  it('renders the recent conversations section', async () => {
    setupHappyPath({ convCount: 2 });
    renderDashboard();
    expect(await screen.findByTestId('recent-conversations')).toBeInTheDocument();
  });

  it('shows empty state when no conversations', async () => {
    setupHappyPath({ convCount: 0, convTotal: 0 });
    renderDashboard();
    await screen.findByTestId('recent-conversations');
    expect(screen.getByTestId('no-recent-conversations')).toBeInTheDocument();
  });

  it('shows conversation items', async () => {
    setupHappyPath({ convCount: 3 });
    renderDashboard();
    await screen.findByTestId('recent-conversations');
    const items = screen.getAllByTestId('recent-conversation-item');
    expect(items).toHaveLength(3);
  });

  it('shows at most 5 recent conversations', async () => {
    vi.mocked(listDocuments).mockResolvedValue(makeDocsResponse());
    vi.mocked(listConversations).mockResolvedValue(makeConvsResponse(10, 10));
    vi.mocked(getHealth).mockResolvedValue(makeHealthOk());

    renderDashboard();
    await screen.findByTestId('recent-conversations');
    const items = screen.getAllByTestId('recent-conversation-item');
    expect(items).toHaveLength(5);
  });

  it('navigates to /chat/:id when conversation item is clicked', async () => {
    setupHappyPath({ convCount: 2 });
    renderDashboard();
    await screen.findByTestId('recent-conversations');
    const items = screen.getAllByTestId('recent-conversation-item');
    await userEvent.click(items[0].querySelector('button')!);
    expect(mockNavigate).toHaveBeenCalledWith('/chat/conv-1');
  });
});

describe('Dashboard — quick actions', () => {
  beforeEach(() => {
    setupHappyPath();
    mockNavigate.mockClear();
  });

  it('navigates to /chat when New Chat button clicked', async () => {
    renderDashboard();
    const btn = await screen.findByTestId('btn-new-chat');
    await userEvent.click(btn);
    expect(mockNavigate).toHaveBeenCalledWith('/chat');
  });

  it('navigates to /documents when Ingest Docs button clicked', async () => {
    renderDashboard();
    const btn = await screen.findByTestId('btn-ingest-docs');
    await userEvent.click(btn);
    expect(mockNavigate).toHaveBeenCalledWith('/documents');
  });

  it('navigates to /settings when Settings button clicked', async () => {
    renderDashboard();
    const btn = await screen.findByTestId('btn-settings');
    await userEvent.click(btn);
    expect(mockNavigate).toHaveBeenCalledWith('/settings');
  });
});

describe('Dashboard — API calls', () => {
  beforeEach(() => {
    setupHappyPath();
    mockNavigate.mockClear();
  });

  it('calls listDocuments, listConversations, and getHealth on mount', async () => {
    renderDashboard();
    await waitFor(() => {
      expect(listDocuments).toHaveBeenCalledWith({ page: 1, page_size: 1 });
      expect(listConversations).toHaveBeenCalled();
      expect(getHealth).toHaveBeenCalled();
    });
  });
});
