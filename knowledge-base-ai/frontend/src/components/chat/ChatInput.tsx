/**
 * ChatInput — text area with send button.
 *
 * Behaviors (frontend-contract.md §2.1):
 *  - Enter key submits the message
 *  - Shift+Enter inserts a newline (default textarea behaviour)
 *  - Disabled when `disabled` prop is true (e.g. while streaming)
 *  - Send button disabled when input is empty or when `disabled`
 *  - Clears input after a successful send
 */
import { useState } from 'react';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ChatInputProps {
  onSend: (content: string) => void;
  disabled?: boolean;
  placeholder?: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ChatInput({
  onSend,
  disabled = false,
  placeholder = 'Ask anything about your documents…',
}: ChatInputProps) {
  const [value, setValue] = useState('');

  const canSend = value.trim().length > 0 && !disabled;

  function handleSend() {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue('');
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
    // Shift+Enter falls through to default textarea newline behaviour
  }

  return (
    <div className="chat-input" data-testid="chat-input">
      <textarea
        className="chat-input__textarea"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        placeholder={placeholder}
        rows={1}
        aria-label="Message input"
        data-testid="chat-input-textarea"
      />
      <button
        className="chat-input__send"
        onClick={handleSend}
        disabled={!canSend}
        aria-label="Send message"
        data-testid="chat-input-send"
      >
        Send
      </button>
    </div>
  );
}
