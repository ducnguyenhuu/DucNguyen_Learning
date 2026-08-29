/**
 * ChatView page tests (T053)
 *
 * Strategy: mock `useChat` to control state; let child components render
 * naturally; use MemoryRouter for route params.
 */
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';

// jsdom does not implement scrollIntoView — polyfill it globally
beforeAll(() => {
  window.HTMLElement.prototype.scrollIntoView = vi.fn();
});

import type { ChatMessage, SourceReference } from '../services/types';

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockSendMessage = vi.fn().mockResolvedValue(undefined);
const mockSetActiveSources = vi.fn();
const mockClearError = vi.fn();
const mockNavigate = vi.fn();

const mockUseChatResult = {
  messages: [] as ChatMessage[],
  streaming: false,
  error: null as string | null,
  activeSources: [] as SourceReference[],
  activeConversationId: null as string | null,
  sendMessage: mockSendMessage,
  setActiveSources: mockSetActiveSources,
  clearError: mockClearError,
};

vi.mock('../hooks/useChat', () => ({
  useChat: vi.fn(() => mockUseChatResult),
}));

const mockUseConversationsResult = {
  conversations: [],
  total: 0,
  loading: false,
  error: null,
  deleting: false,
  deleteError: null,
  clearing: false,
  clearError: null,
  deleteConversation: vi.fn().mockResolvedValue(undefined),
  clearAll: vi.fn().mockResolvedValue(undefined),
  refresh: vi.fn(),
};

vi.mock('../hooks/useConversations', () => ({
  useConversations: vi.fn(() => mockUseConversationsResult),
}));

// Partially mock react-router-dom — keep MemoryRouter / Routes / Route
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

import { useChat } from '../hooks/useChat';
import ChatView from './ChatView';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderAtPath(path = '/chat') {
  const routePattern = path.startsWith('/chat/') ? '/chat/:conversationId' : '/chat';
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path={routePattern} element={<ChatView />} />
      </Routes>
    </MemoryRouter>,
  );
}

const makeMessage = (overrides: Partial<ChatMessage> = {}): ChatMessage => ({
  id: 'msg-1',
  role: 'user',
  content: 'Hello',
  source_references: null,
  created_at: '2024-01-01T00:00:00Z',
  ...overrides,
});

const makeSource = (overrides: Partial<SourceReference> = {}): SourceReference => ({
  document_id: 'doc-1',
  file_name: 'report.pdf',
  page_number: 1,
  relevance_score: 0.85,
  ...overrides,
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('ChatView — layout', () => {
  beforeEach(() => {
    vi.mocked(useChat).mockReturnValue({ ...mockUseChatResult });
    mockNavigate.mockClear();
  });

  it('renders the chat view container', () => {
    renderAtPath();
    expect(screen.getByTestId('chat-view')).toBeInTheDocument();
  });

  it('renders the conversation sidebar', () => {
    renderAtPath();
    expect(screen.getByTestId('conversation-sidebar')).toBeInTheDocument();
  });

  it('renders the New Chat button', () => {
    renderAtPath();
    expect(screen.getByRole('button', { name: /new chat/i })).toBeInTheDocument();
  });

  it('New Chat button navigates to /chat', async () => {
    renderAtPath('/chat/conv-123');
    const btn = screen.getByRole('button', { name: /new chat/i });
    await userEvent.click(btn);
    expect(mockNavigate).toHaveBeenCalledWith('/chat');
  });

  it('renders ChatInput', () => {
    renderAtPath();
    expect(screen.getByTestId('chat-input')).toBeInTheDocument();
  });

  it('renders SourcePanel', () => {
    renderAtPath();
    expect(screen.getByTestId('source-panel')).toBeInTheDocument();
  });
});

describe('ChatView — welcome / empty state', () => {
  beforeEach(() => {
    vi.mocked(useChat).mockReturnValue({ ...mockUseChatResult, messages: [] });
  });

  it('shows the welcome message when no messages', () => {
    renderAtPath();
    expect(screen.getByTestId('welcome-message')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /ask anything/i })).toBeInTheDocument();
  });

  it('shows three example prompts', () => {
    renderAtPath();
    expect(screen.getByTestId('example-prompts')).toBeInTheDocument();
    const buttons = screen.getAllByRole('button', { name: /.+/ });
    const promptBtns = buttons.filter((b) => !['new chat', '×'].some((s) => b.textContent?.toLowerCase().includes(s)));
    expect(promptBtns.length).toBeGreaterThanOrEqual(3);
  });

  it('does NOT show message list when empty', () => {
    renderAtPath();
    expect(screen.queryByTestId('message-list')).not.toBeInTheDocument();
  });
});

describe('ChatView — message list', () => {
  const messages: ChatMessage[] = [
    makeMessage({ id: 'u1', role: 'user', content: 'What is AI?' }),
    makeMessage({ id: 'a1', role: 'assistant', content: 'AI is…' }),
  ];

  beforeEach(() => {
    vi.mocked(useChat).mockReturnValue({ ...mockUseChatResult, messages });
  });

  it('hides welcome when messages exist', () => {
    renderAtPath();
    expect(screen.queryByTestId('welcome-message')).not.toBeInTheDocument();
  });

  it('shows message list', () => {
    renderAtPath();
    expect(screen.getByTestId('message-list')).toBeInTheDocument();
  });

  it('renders a MessageBubble for each message', () => {
    renderAtPath();
    expect(screen.getByTestId('message-bubble-user')).toBeInTheDocument();
    expect(screen.getByTestId('message-bubble-assistant')).toBeInTheDocument();
  });
});

describe('ChatView — streaming state', () => {
  beforeEach(() => {
    vi.mocked(useChat).mockReturnValue({
      ...mockUseChatResult,
      messages: [makeMessage()],
      streaming: true,
    });
  });

  it('shows typing indicator when streaming', () => {
    renderAtPath();
    expect(screen.getByTestId('typing-indicator')).toBeInTheDocument();
  });

  it('disables ChatInput when streaming', () => {
    renderAtPath();
    expect(screen.getByTestId('chat-input-textarea')).toBeDisabled();
  });
});

describe('ChatView — error state', () => {
  beforeEach(() => {
    vi.mocked(useChat).mockReturnValue({ ...mockUseChatResult, error: 'Something went wrong' });
    mockClearError.mockClear();
  });

  it('displays error alert', () => {
    renderAtPath();
    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent('Something went wrong');
  });

  it('calls clearError when dismiss button clicked', async () => {
    renderAtPath();
    const dismiss = screen.getByRole('button', { name: /dismiss error/i });
    await userEvent.click(dismiss);
    expect(mockClearError).toHaveBeenCalledOnce();
  });
});

describe('ChatView — send message', () => {
  beforeEach(() => {
    vi.mocked(useChat).mockReturnValue({ ...mockUseChatResult });
    mockSendMessage.mockClear();
  });

  it('calls sendMessage when user types and presses Enter', async () => {
    renderAtPath();
    const textarea = screen.getByTestId('chat-input-textarea');
    await userEvent.type(textarea, 'Hello world{Enter}');
    expect(mockSendMessage).toHaveBeenCalledWith('Hello world');
  });

  it('calls sendMessage when example prompt is clicked', async () => {
    renderAtPath();
    // Find first example prompt button
    const exampleBtns = screen.getAllByRole('button');
    const promptBtn = exampleBtns.find((b) =>
      b.textContent?.includes('key topics'),
    );
    expect(promptBtn).toBeTruthy();
    await userEvent.click(promptBtn!);
    expect(mockSendMessage).toHaveBeenCalledWith(
      'What are the key topics covered in my documents?',
    );
  });
});

describe('ChatView — source panel', () => {
  const sources: SourceReference[] = [makeSource(), makeSource({ file_name: 'notes.pdf', document_id: 'doc-2' })];

  beforeEach(() => {
    vi.mocked(useChat).mockReturnValue({
      ...mockUseChatResult,
      activeSources: sources,
    });
    mockSetActiveSources.mockClear();
  });

  it('passes activeSources to SourcePanel', () => {
    renderAtPath();
    expect(screen.getAllByTestId('source-panel-item')).toHaveLength(2);
  });

  it('calls setActiveSources([]) when SourcePanel close is clicked', async () => {
    renderAtPath();
    const closeBtn = screen.getByTestId('source-panel-close');
    await userEvent.click(closeBtn);
    expect(mockSetActiveSources).toHaveBeenCalledWith([]);
  });
});

describe('ChatView — navigation', () => {
  beforeEach(() => {
    mockNavigate.mockClear();
  });

  it('navigates to /chat/{id} when new activeConversationId appears', () => {
    // Start at /chat (no conversationId), hook returns an activeConversationId
    vi.mocked(useChat).mockReturnValue({
      ...mockUseChatResult,
      activeConversationId: 'new-conv-456',
    });
    renderAtPath('/chat');
    expect(mockNavigate).toHaveBeenCalledWith('/chat/new-conv-456', { replace: true });
  });

  it('does NOT navigate if conversationId already in URL', () => {
    vi.mocked(useChat).mockReturnValue({
      ...mockUseChatResult,
      activeConversationId: 'conv-123',
    });
    renderAtPath('/chat/conv-123');
    expect(mockNavigate).not.toHaveBeenCalledWith(
      expect.stringContaining('/chat/conv'),
      expect.any(Object),
    );
  });

  it('passes conversationId from URL to useChat', () => {
    vi.mocked(useChat).mockReturnValue({ ...mockUseChatResult });
    renderAtPath('/chat/my-conv');
    expect(vi.mocked(useChat)).toHaveBeenCalledWith('my-conv');
  });

  it('passes null to useChat when no conversationId in URL', () => {
    vi.mocked(useChat).mockReturnValue({ ...mockUseChatResult });
    renderAtPath('/chat');
    expect(vi.mocked(useChat)).toHaveBeenCalledWith(null);
  });
});
