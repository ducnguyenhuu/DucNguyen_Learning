/**
 * Unit tests for MessageBubble component.
 *
 * Covers:
 *  - Role-based class names and test IDs
 *  - User messages render plain text
 *  - Assistant messages use markdown rendering
 *  - formatMarkdown helper output
 *  - No citations when source_references is null or empty
 *  - Citation badges rendered for each source reference
 *  - onSourceClick called with the full sources array when any badge clicked
 *  - Badge aria-label includes file name and page number
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MessageBubble, formatMarkdown } from './MessageBubble';
import type { ChatMessage } from './MessageBubble';
import type { SourceReference } from '../../services/types';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeMsg(overrides: Partial<ChatMessage> = {}): ChatMessage {
  return {
    id: 'msg-1',
    role: 'user',
    content: 'Hello world',
    source_references: null,
    created_at: '2026-03-05T12:00:00Z',
    ...overrides,
  };
}

function makeRef(overrides: Partial<SourceReference> = {}): SourceReference {
  return {
    document_id: 'doc-1',
    file_name: 'guide.pdf',
    page_number: 12,
    relevance_score: 0.91,
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// formatMarkdown helper
// ---------------------------------------------------------------------------

describe('formatMarkdown', () => {
  it('escapes HTML special characters', () => {
    const result = formatMarkdown('<script>alert("xss")</script>');
    expect(result).not.toContain('<script>');
    expect(result).toContain('&lt;script&gt;');
  });

  it('converts **bold** to <strong>', () => {
    expect(formatMarkdown('**hello**')).toContain('<strong>hello</strong>');
  });

  it('converts *italic* to <em>', () => {
    expect(formatMarkdown('*italic*')).toContain('<em>italic</em>');
  });

  it('converts `code` to <code>', () => {
    expect(formatMarkdown('`code`')).toContain('<code>code</code>');
  });

  it('converts newlines to <br>', () => {
    expect(formatMarkdown('line1\nline2')).toContain('<br>');
  });
});

// ---------------------------------------------------------------------------
// Role rendering
// ---------------------------------------------------------------------------

describe('MessageBubble — role classes', () => {
  it('applies message-bubble--user class for user messages', () => {
    const { container } = render(<MessageBubble message={makeMsg({ role: 'user' })} />);
    expect(container.firstChild).toHaveClass('message-bubble--user');
  });

  it('applies message-bubble--assistant class for assistant messages', () => {
    const { container } = render(
      <MessageBubble message={makeMsg({ role: 'assistant', content: 'A' })} />,
    );
    expect(container.firstChild).toHaveClass('message-bubble--assistant');
  });

  it('sets data-testid="message-bubble-user" for user messages', () => {
    render(<MessageBubble message={makeMsg({ role: 'user' })} />);
    expect(screen.getByTestId('message-bubble-user')).toBeInTheDocument();
  });

  it('sets data-testid="message-bubble-assistant" for assistant messages', () => {
    render(
      <MessageBubble message={makeMsg({ role: 'assistant', content: 'Hi' })} />,
    );
    expect(screen.getByTestId('message-bubble-assistant')).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Content rendering
// ---------------------------------------------------------------------------

describe('MessageBubble — content', () => {
  it('renders user message content as plain text inside <p>', () => {
    render(<MessageBubble message={makeMsg({ role: 'user', content: 'My question?' })} />);
    expect(screen.getByText('My question?').tagName).toBe('P');
  });

  it('renders assistant message inside a markdown container', () => {
    const { container } = render(
      <MessageBubble
        message={makeMsg({ role: 'assistant', content: '**Bold** answer' })}
      />,
    );
    const md = container.querySelector('.message-bubble__markdown');
    expect(md).not.toBeNull();
    expect(md?.innerHTML).toContain('<strong>Bold</strong>');
  });

  it('displays assistant message content', () => {
    render(
      <MessageBubble message={makeMsg({ role: 'assistant', content: 'The answer is 42.' })} />,
    );
    expect(screen.getByText('The answer is 42.')).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Citations
// ---------------------------------------------------------------------------

describe('MessageBubble — citations', () => {
  it('shows no citation badges when source_references is null', () => {
    render(<MessageBubble message={makeMsg({ source_references: null })} />);
    expect(screen.queryByTestId('citations')).toBeNull();
  });

  it('shows no citation badges when source_references is empty', () => {
    render(<MessageBubble message={makeMsg({ source_references: [] })} />);
    expect(screen.queryByTestId('citations')).toBeNull();
  });

  it('renders one badge per source reference', () => {
    const refs = [makeRef({ file_name: 'a.pdf' }), makeRef({ file_name: 'b.pdf' })];
    render(
      <MessageBubble
        message={makeMsg({ role: 'assistant', source_references: refs })}
      />,
    );
    const badges = screen.getAllByTestId('citation-badge');
    expect(badges).toHaveLength(2);
  });

  it('badge text includes file name and page number', () => {
    const refs = [makeRef({ file_name: 'guide.pdf', page_number: 5 })];
    render(
      <MessageBubble
        message={makeMsg({ role: 'assistant', source_references: refs })}
      />,
    );
    expect(screen.getByText('guide.pdf p.5')).toBeInTheDocument();
  });

  it('badge text omits page when page_number is null', () => {
    const refs = [makeRef({ file_name: 'readme.md', page_number: null })];
    render(
      <MessageBubble
        message={makeMsg({ role: 'assistant', source_references: refs })}
      />,
    );
    expect(screen.getByText('readme.md')).toBeInTheDocument();
    expect(screen.queryByText(/p\./)).toBeNull();
  });

  it('calls onSourceClick with full sources array when badge clicked', () => {
    const onSourceClick = vi.fn();
    const refs = [makeRef(), makeRef({ file_name: 'other.pdf' })];
    render(
      <MessageBubble
        message={makeMsg({ role: 'assistant', source_references: refs })}
        onSourceClick={onSourceClick}
      />,
    );
    fireEvent.click(screen.getAllByTestId('citation-badge')[0]);
    expect(onSourceClick).toHaveBeenCalledWith(refs);
  });

  it('does not throw when onSourceClick is not provided', () => {
    const refs = [makeRef()];
    render(
      <MessageBubble
        message={makeMsg({ role: 'assistant', source_references: refs })}
      />,
    );
    expect(() => fireEvent.click(screen.getByTestId('citation-badge'))).not.toThrow();
  });
});
