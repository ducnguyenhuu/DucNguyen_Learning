/**
 * Tests for ConversationSidebar component (T056)
 *
 * Strategy: mock useConversations; render with react-testing-library.
 */
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { Conversation } from '../../services/types';
import { ConversationSidebar } from './ConversationSidebar';

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockDeleteConversation = vi.fn().mockResolvedValue(undefined);
const mockClearAll = vi.fn().mockResolvedValue(undefined);
const mockRefresh = vi.fn();

const defaultHookResult = {
  conversations: [] as Conversation[],
  total: 0,
  loading: false,
  error: null as string | null,
  deleting: false,
  deleteError: null as string | null,
  clearing: false,
  clearError: null as string | null,
  deleteConversation: mockDeleteConversation,
  clearAll: mockClearAll,
  refresh: mockRefresh,
};

vi.mock('../../hooks/useConversations', () => ({
  useConversations: vi.fn(() => defaultHookResult),
}));

import { useConversations } from '../../hooks/useConversations';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const NOW = new Date('2026-03-05T12:00:00Z').getTime();

function makeConv(
  id: string,
  title: string | null = `Chat ${id}`,
  updatedAt = '2026-03-05T11:00:00Z',
): Conversation {
  return {
    id,
    title,
    preview: `Preview for ${id}`,
    message_count: 2,
    created_at: '2026-03-05T10:00:00Z',
    updated_at: updatedAt,
  };
}

const defaultProps = {
  activeConversationId: null as string | null,
  onSelectConversation: vi.fn(),
  onNewChat: vi.fn(),
  onActiveConversationDeleted: vi.fn(),
};

function renderSidebar(
  props: Partial<typeof defaultProps> = {},
  hookOverrides: Partial<typeof defaultHookResult> = {},
) {
  vi.mocked(useConversations).mockReturnValue({ ...defaultHookResult, ...hookOverrides });
  return render(
    <ConversationSidebar
      {...defaultProps}
      {...props}
    />,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.setSystemTime(NOW);
});

// ---------------------------------------------------------------------------
// Layout
// ---------------------------------------------------------------------------

describe('ConversationSidebar — layout', () => {
  it('renders the sidebar container', () => {
    renderSidebar();
    expect(screen.getByTestId('conversation-sidebar')).toBeInTheDocument();
  });

  it('renders New Chat button', () => {
    renderSidebar();
    expect(screen.getByTestId('new-chat-btn')).toBeInTheDocument();
  });

  it('renders Clear All button', () => {
    renderSidebar();
    expect(screen.getByTestId('clear-all-btn')).toBeInTheDocument();
  });

  it('shows empty state when no conversations', () => {
    renderSidebar();
    expect(screen.getByTestId('sidebar-empty')).toBeInTheDocument();
  });

  it('does not show empty state when conversations exist', () => {
    renderSidebar({}, { conversations: [makeConv('c1')] });
    expect(screen.queryByTestId('sidebar-empty')).not.toBeInTheDocument();
  });

  it('Clear All is disabled when no conversations', () => {
    renderSidebar();
    expect(screen.getByTestId('clear-all-btn')).toBeDisabled();
  });

  it('Clear All is enabled when conversations exist', () => {
    renderSidebar({}, { conversations: [makeConv('c1')] });
    expect(screen.getByTestId('clear-all-btn')).not.toBeDisabled();
  });
});

// ---------------------------------------------------------------------------
// Loading / error states
// ---------------------------------------------------------------------------

describe('ConversationSidebar — loading / error', () => {
  it('shows loading indicator when loading', () => {
    renderSidebar({}, { loading: true });
    expect(screen.getByTestId('sidebar-loading')).toBeInTheDocument();
  });

  it('hides conversation list while loading', () => {
    renderSidebar({}, { loading: true, conversations: [makeConv('c1')] });
    expect(screen.queryByTestId('conversation-item')).not.toBeInTheDocument();
  });

  it('shows fetch error', () => {
    renderSidebar({}, { error: 'Failed to load' });
    expect(screen.getByRole('alert')).toHaveTextContent('Failed to load');
  });

  it('shows deleteError', () => {
    renderSidebar({}, { deleteError: 'Delete failed' });
    expect(screen.getByRole('alert')).toHaveTextContent('Delete failed');
  });

  it('shows clearError', () => {
    renderSidebar({}, { clearError: 'Clear failed' });
    expect(screen.getByRole('alert')).toHaveTextContent('Clear failed');
  });
});

// ---------------------------------------------------------------------------
// Conversation list rendering
// ---------------------------------------------------------------------------

describe('ConversationSidebar — conversation list', () => {
  it('renders one item per conversation', () => {
    renderSidebar({}, { conversations: [makeConv('c1'), makeConv('c2'), makeConv('c3')] });
    expect(screen.getAllByTestId('conversation-item')).toHaveLength(3);
  });

  it('renders conversation title', () => {
    renderSidebar({}, { conversations: [makeConv('c1', 'My Chat')] });
    expect(screen.getByTestId('conversation-label')).toHaveTextContent('My Chat');
  });

  it('falls back to preview when title is null', () => {
    const conv = makeConv('c1', null);
    renderSidebar({}, { conversations: [conv] });
    expect(screen.getByTestId('conversation-label')).toHaveTextContent(`Preview for c1`);
  });

  it('shows "New conversation" when both title and preview are null', () => {
    const conv: Conversation = { ...makeConv('c1', null), preview: null };
    renderSidebar({}, { conversations: [conv] });
    expect(screen.getByTestId('conversation-label')).toHaveTextContent('New conversation');
  });

  it('marks active conversation with aria-current', () => {
    renderSidebar(
      { activeConversationId: 'c2' },
      { conversations: [makeConv('c1'), makeConv('c2'), makeConv('c3')] },
    );
    const btns = screen.getAllByTestId('conversation-select-btn');
    const active = btns.find((b) => b.getAttribute('aria-current') === 'page');
    expect(active).toBeTruthy();
  });

  it('renders a delete button per conversation', () => {
    renderSidebar({}, { conversations: [makeConv('c1'), makeConv('c2')] });
    expect(screen.getAllByTestId('conversation-delete-btn')).toHaveLength(2);
  });
});

// ---------------------------------------------------------------------------
// New Chat
// ---------------------------------------------------------------------------

describe('ConversationSidebar — New Chat button', () => {
  it('calls onNewChat when clicked', async () => {
    const onNewChat = vi.fn();
    renderSidebar({ onNewChat });
    await userEvent.click(screen.getByTestId('new-chat-btn'));
    expect(onNewChat).toHaveBeenCalledOnce();
  });
});

// ---------------------------------------------------------------------------
// Selecting a conversation
// ---------------------------------------------------------------------------

describe('ConversationSidebar — select conversation', () => {
  it('calls onSelectConversation with id when clicked', async () => {
    const onSelectConversation = vi.fn();
    renderSidebar(
      { onSelectConversation },
      { conversations: [makeConv('c1'), makeConv('c2')] },
    );
    const btns = screen.getAllByTestId('conversation-select-btn');
    await userEvent.click(btns[1]); // second item = c2
    expect(onSelectConversation).toHaveBeenCalledWith('c2');
  });
});

// ---------------------------------------------------------------------------
// Single delete with confirmation
// ---------------------------------------------------------------------------

describe('ConversationSidebar — delete single conversation', () => {
  it('shows confirm dialog when delete button clicked', async () => {
    renderSidebar({}, { conversations: [makeConv('c1')] });
    await userEvent.click(screen.getByTestId('conversation-delete-btn'));
    expect(screen.getByTestId('confirm-dialog')).toBeInTheDocument();
  });

  it('calls deleteConversation with id on confirm', async () => {
    renderSidebar({}, { conversations: [makeConv('c1')] });
    await userEvent.click(screen.getByTestId('conversation-delete-btn'));
    await userEvent.click(screen.getByTestId('confirm-ok'));
    expect(mockDeleteConversation).toHaveBeenCalledWith('c1');
  });

  it('closes dialog on cancel without deleting', async () => {
    renderSidebar({}, { conversations: [makeConv('c1')] });
    await userEvent.click(screen.getByTestId('conversation-delete-btn'));
    await userEvent.click(screen.getByTestId('confirm-cancel'));
    expect(mockDeleteConversation).not.toHaveBeenCalled();
    expect(screen.queryByTestId('confirm-dialog')).not.toBeInTheDocument();
  });

  it('calls onActiveConversationDeleted when active conversation deleted', async () => {
    const onActiveConversationDeleted = vi.fn();
    renderSidebar(
      { activeConversationId: 'c1', onActiveConversationDeleted },
      { conversations: [makeConv('c1')] },
    );
    await userEvent.click(screen.getByTestId('conversation-delete-btn'));
    await userEvent.click(screen.getByTestId('confirm-ok'));
    expect(onActiveConversationDeleted).toHaveBeenCalledOnce();
  });

  it('does NOT call onActiveConversationDeleted when deleting non-active conversation', async () => {
    const onActiveConversationDeleted = vi.fn();
    renderSidebar(
      { activeConversationId: 'c2', onActiveConversationDeleted },
      { conversations: [makeConv('c1'), makeConv('c2')] },
    );
    // click delete on first item (c1) which is not active
    const deleteBtns = screen.getAllByTestId('conversation-delete-btn');
    await userEvent.click(deleteBtns[0]);
    await userEvent.click(screen.getByTestId('confirm-ok'));
    expect(onActiveConversationDeleted).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// Clear All with confirmation
// ---------------------------------------------------------------------------

describe('ConversationSidebar — clear all', () => {
  it('shows confirm dialog when Clear All clicked', async () => {
    renderSidebar({}, { conversations: [makeConv('c1')] });
    await userEvent.click(screen.getByTestId('clear-all-btn'));
    expect(screen.getByTestId('confirm-dialog')).toBeInTheDocument();
  });

  it('calls clearAll on confirm', async () => {
    renderSidebar({}, { conversations: [makeConv('c1')] });
    await userEvent.click(screen.getByTestId('clear-all-btn'));
    await userEvent.click(screen.getByTestId('confirm-ok'));
    expect(mockClearAll).toHaveBeenCalledOnce();
  });

  it('does not call clearAll on cancel', async () => {
    renderSidebar({}, { conversations: [makeConv('c1')] });
    await userEvent.click(screen.getByTestId('clear-all-btn'));
    await userEvent.click(screen.getByTestId('confirm-cancel'));
    expect(mockClearAll).not.toHaveBeenCalled();
  });

  it('calls onActiveConversationDeleted after clearAll when active conversation exists', async () => {
    const onActiveConversationDeleted = vi.fn();
    renderSidebar(
      { activeConversationId: 'c1', onActiveConversationDeleted },
      { conversations: [makeConv('c1'), makeConv('c2')] },
    );
    await userEvent.click(screen.getByTestId('clear-all-btn'));
    await userEvent.click(screen.getByTestId('confirm-ok'));
    expect(onActiveConversationDeleted).toHaveBeenCalledOnce();
  });

  it('does not call onActiveConversationDeleted when no active conversation', async () => {
    const onActiveConversationDeleted = vi.fn();
    renderSidebar(
      { activeConversationId: null, onActiveConversationDeleted },
      { conversations: [makeConv('c1')] },
    );
    await userEvent.click(screen.getByTestId('clear-all-btn'));
    await userEvent.click(screen.getByTestId('confirm-ok'));
    expect(onActiveConversationDeleted).not.toHaveBeenCalled();
  });

  it('hides confirm dialog after cancel', async () => {
    renderSidebar({}, { conversations: [makeConv('c1')] });
    await userEvent.click(screen.getByTestId('clear-all-btn'));
    await userEvent.click(screen.getByTestId('confirm-cancel'));
    expect(screen.queryByTestId('confirm-dialog')).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Accessibility
// ---------------------------------------------------------------------------

describe('ConversationSidebar — accessibility', () => {
  it('sidebar nav has aria-label', () => {
    renderSidebar();
    expect(screen.getByRole('navigation', { name: /conversations/i })).toBeInTheDocument();
  });

  it('confirm dialog has role=dialog', async () => {
    renderSidebar({}, { conversations: [makeConv('c1')] });
    await userEvent.click(screen.getByTestId('conversation-delete-btn'));
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });
});
