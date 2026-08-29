/**
 * Unit tests for ChatInput component.
 *
 * Covers:
 *  - Renders textarea and send button
 *  - Enter key triggers onSend with trimmed content
 *  - Shift+Enter does NOT trigger onSend
 *  - Clears input value after send
 *  - disabled prop disables textarea and button
 *  - Send button disabled when input is empty
 *  - Send button disabled when input is only whitespace
 *  - Does not call onSend when content is whitespace
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ChatInput } from './ChatInput';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function setup(props: Partial<React.ComponentProps<typeof ChatInput>> = {}) {
  const onSend = vi.fn();
  const utils = render(<ChatInput onSend={onSend} {...props} />);
  const textarea = screen.getByTestId<HTMLTextAreaElement>('chat-input-textarea');
  const sendBtn = screen.getByTestId<HTMLButtonElement>('chat-input-send');
  return { onSend, textarea, sendBtn, ...utils };
}

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------

describe('ChatInput — rendering', () => {
  it('renders the textarea', () => {
    setup();
    expect(screen.getByTestId('chat-input-textarea')).toBeInTheDocument();
  });

  it('renders the send button', () => {
    setup();
    expect(screen.getByTestId('chat-input-send')).toBeInTheDocument();
  });

  it('applies custom placeholder', () => {
    render(<ChatInput onSend={vi.fn()} placeholder="Type here" />);
    expect(screen.getByPlaceholderText('Type here')).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Send behaviour
// ---------------------------------------------------------------------------

describe('ChatInput — send on Enter', () => {
  it('calls onSend with trimmed content when Enter is pressed', async () => {
    const { onSend, textarea } = setup();
    await userEvent.type(textarea, 'Hello{Enter}');
    expect(onSend).toHaveBeenCalledWith('Hello');
  });

  it('does NOT call onSend when Shift+Enter is pressed', async () => {
    const { onSend, textarea } = setup();
    await userEvent.type(textarea, 'line1{Shift>}{Enter}{/Shift}');
    expect(onSend).not.toHaveBeenCalled();
  });

  it('calls onSend when send button is clicked', async () => {
    const { onSend, textarea, sendBtn } = setup();
    await userEvent.type(textarea, 'Hello');
    await userEvent.click(sendBtn);
    expect(onSend).toHaveBeenCalledWith('Hello');
  });

  it('clears the textarea after send', async () => {
    const { textarea } = setup();
    await userEvent.type(textarea, 'Hello{Enter}');
    expect(textarea.value).toBe('');
  });

  it('trims whitespace before calling onSend', async () => {
    const { onSend, textarea } = setup();
    await userEvent.type(textarea, '  hello  {Enter}');
    expect(onSend).toHaveBeenCalledWith('hello');
  });

  it('does NOT call onSend when input is only whitespace', async () => {
    const { onSend, textarea } = setup();
    await userEvent.type(textarea, '   {Enter}');
    expect(onSend).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// Disabled state
// ---------------------------------------------------------------------------

describe('ChatInput — disabled state', () => {
  it('disables the textarea when disabled=true', () => {
    const { textarea } = setup({ disabled: true });
    expect(textarea).toBeDisabled();
  });

  it('disables the send button when disabled=true', () => {
    const { sendBtn } = setup({ disabled: true });
    expect(sendBtn).toBeDisabled();
  });

  it('disables the send button when input is empty', () => {
    const { sendBtn } = setup();
    expect(sendBtn).toBeDisabled();
  });

  it('enables the send button when input has content', async () => {
    const { textarea, sendBtn } = setup();
    await userEvent.type(textarea, 'Hi');
    expect(sendBtn).not.toBeDisabled();
  });

  it('does NOT call onSend when disabled even via Enter', () => {
    const { onSend, textarea } = setup({ disabled: true });
    // Type via fireEvent to bypass disabled check
    fireEvent.change(textarea, { target: { value: 'Hi' } });
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false });
    expect(onSend).not.toHaveBeenCalled();
  });
});
