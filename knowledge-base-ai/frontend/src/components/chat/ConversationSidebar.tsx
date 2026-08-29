/**
 * ConversationSidebar — scrollable list of past conversations.
 *
 * Responsibilities (frontend-contract.md §2.1):
 *  - "New Chat" button navigates to /chat
 *  - "Clear All" button shows confirmation before bulk-deleting
 *  - Conversation list sorted by updated_at DESC (hook returns them sorted)
 *  - Each row: click to navigate, delete button with confirmation
 *  - After clearing / deleting the active conversation, parent is notified
 *    via onActiveConversationDeleted so ChatView can redirect
 */
import { useState } from 'react';

import { useConversations } from '../../hooks/useConversations';
import type { Conversation } from '../../services/types';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ConversationSidebarProps {
  activeConversationId?: string | null;
  onSelectConversation: (id: string) => void;
  onNewChat: () => void;
  /** Called when the currently-active conversation is deleted or all are cleared. */
  onActiveConversationDeleted?: () => void;
}

// ---------------------------------------------------------------------------
// Sub-component: confirmation dialog
// ---------------------------------------------------------------------------

interface ConfirmDialogProps {
  message: string;
  onConfirm: () => void;
  onCancel: () => void;
}

function ConfirmDialog({ message, onConfirm, onCancel }: ConfirmDialogProps) {
  return (
    <div
      className="confirm-dialog-overlay"
      data-testid="confirm-dialog"
      role="dialog"
      aria-modal="true"
      aria-label="Confirm action"
    >
      <div className="confirm-dialog">
        <p className="confirm-dialog__message">{message}</p>
        <div className="confirm-dialog__actions">
          <button
            type="button"
            className="confirm-dialog__cancel"
            data-testid="confirm-cancel"
            onClick={onCancel}
          >
            Cancel
          </button>
          <button
            type="button"
            className="confirm-dialog__confirm confirm-dialog__confirm--danger"
            data-testid="confirm-ok"
            onClick={onConfirm}
          >
            Delete
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function ConversationSidebar({
  activeConversationId,
  onSelectConversation,
  onNewChat,
  onActiveConversationDeleted,
}: ConversationSidebarProps) {
  const {
    conversations,
    loading,
    error,
    deleting,
    deleteError,
    clearing,
    clearError,
    deleteConversation,
    clearAll,
  } = useConversations();

  // Which conversation is pending single-delete confirmation
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);
  // Whether the "clear all" dialog is open
  const [showClearConfirm, setShowClearConfirm] = useState(false);

  // ---------------------------------------------------------------------------
  // Handlers
  // ---------------------------------------------------------------------------

  async function handleConfirmDelete() {
    if (!pendingDeleteId) return;
    const wasActive = pendingDeleteId === activeConversationId;
    await deleteConversation(pendingDeleteId);
    setPendingDeleteId(null);
    if (wasActive) {
      onActiveConversationDeleted?.();
    }
  }

  async function handleConfirmClearAll() {
    await clearAll();
    setShowClearConfirm(false);
    if (activeConversationId) {
      onActiveConversationDeleted?.();
    }
  }

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------

  function formatRelativeTime(updatedAt: string): string {
    const diff = Date.now() - new Date(updatedAt).getTime();
    const mins = Math.floor(diff / 60_000);
    if (mins < 60) return mins <= 1 ? 'just now' : `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
  }

  function getConversationLabel(conv: Conversation): string {
    if (conv.title) return conv.title;
    if (conv.preview) return conv.preview;
    return 'New conversation';
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <nav
      className="conversation-sidebar"
      data-testid="conversation-sidebar"
      aria-label="Conversations"
    >
      {/* Header actions */}
      <div className="conversation-sidebar__header">
        <button
          type="button"
          className="conversation-sidebar__new-chat"
          data-testid="new-chat-btn"
          onClick={onNewChat}
        >
          + New Chat
        </button>
        <button
          type="button"
          className="conversation-sidebar__clear-all"
          data-testid="clear-all-btn"
          onClick={() => setShowClearConfirm(true)}
          disabled={conversations.length === 0 || clearing}
          aria-label="Clear all conversations"
        >
          🗑 Clear All
        </button>
      </div>

      {/* Error banners */}
      {(error || deleteError || clearError) && (
        <p
          className="conversation-sidebar__error"
          data-testid="sidebar-error"
          role="alert"
        >
          {error ?? deleteError ?? clearError}
        </p>
      )}

      {/* Loading state */}
      {loading && (
        <p
          className="conversation-sidebar__loading"
          data-testid="sidebar-loading"
        >
          Loading…
        </p>
      )}

      {/* Conversation list */}
      {!loading && conversations.length === 0 && !error && (
        <p
          className="conversation-sidebar__empty"
          data-testid="sidebar-empty"
        >
          No conversations yet
        </p>
      )}

      {!loading && (
      <ul
        className="conversation-sidebar__list"
        data-testid="conversation-list"
      >
        {conversations.map((conv) => {
          const isActive = conv.id === activeConversationId;
          return (
            <li
              key={conv.id}
              className={`conversation-sidebar__item${isActive ? ' conversation-sidebar__item--active' : ''}`}
              data-testid="conversation-item"
              data-active={isActive ? 'true' : undefined}
            >
              <button
                type="button"
                className="conversation-sidebar__conv-btn"
                data-testid="conversation-select-btn"
                onClick={() => onSelectConversation(conv.id)}
                aria-current={isActive ? 'page' : undefined}
              >
                <span
                  className="conversation-sidebar__conv-label"
                  data-testid="conversation-label"
                >
                  {getConversationLabel(conv)}
                </span>
                <span
                  className="conversation-sidebar__conv-time"
                  data-testid="conversation-time"
                >
                  {formatRelativeTime(conv.updated_at)}
                </span>
              </button>

              <button
                type="button"
                className="conversation-sidebar__delete-btn"
                data-testid="conversation-delete-btn"
                aria-label={`Delete conversation ${getConversationLabel(conv)}`}
                onClick={(e) => {
                  e.stopPropagation();
                  setPendingDeleteId(conv.id);
                }}
                disabled={deleting}
              >
                ×
              </button>
            </li>
          );
        })}
      </ul>
      )}

      {/* Single-delete confirmation */}
      {pendingDeleteId && (
        <ConfirmDialog
          message="Delete this conversation? This cannot be undone."
          onConfirm={() => void handleConfirmDelete()}
          onCancel={() => setPendingDeleteId(null)}
        />
      )}

      {/* Clear-all confirmation */}
      {showClearConfirm && (
        <ConfirmDialog
          message="Delete all conversations? This cannot be undone."
          onConfirm={() => void handleConfirmClearAll()}
          onCancel={() => setShowClearConfirm(false)}
        />
      )}
    </nav>
  );
}
