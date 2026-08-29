/**
 * MessageBubble — renders a single chat message.
 *
 * User messages are shown right-aligned with plain text.
 * Assistant messages are shown left-aligned with basic markdown rendering
 * and clickable source citation badges (per frontend-contract.md §2.1).
 */
import type { ChatMessage, SourceReference } from '../../services/types';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type { ChatMessage };

export interface MessageBubbleProps {
  message: ChatMessage;
  onSourceClick?: (sources: SourceReference[]) => void;
}

// ---------------------------------------------------------------------------
// Markdown helper (minimal renderer — no extra dependency)
// ---------------------------------------------------------------------------

/**
 * Convert a small subset of Markdown to safe HTML.
 *
 * Supported: **bold**, *italic*, `inline code`, and newlines → <br>.
 * All other HTML is escaped first to prevent XSS.
 */
export function formatMarkdown(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/gs, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/gs, '<em>$1</em>')
    .replace(/`(.+?)`/g, '<code>$1</code>')
    .replace(/\n/g, '<br>');
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function MessageBubble({ message, onSourceClick }: MessageBubbleProps) {
  const isUser = message.role === 'user';
  const hasSources =
    message.source_references !== null && message.source_references.length > 0;

  return (
    <div
      className={`message-bubble ${isUser ? 'message-bubble--user' : 'message-bubble--assistant'}`}
      data-testid={`message-bubble-${message.role}`}
    >
      <div className="message-bubble__content">
        {isUser ? (
          <p className="message-bubble__text">{message.content}</p>
        ) : (
          <div
            className="message-bubble__markdown"
            dangerouslySetInnerHTML={{ __html: formatMarkdown(message.content) }}
          />
        )}
      </div>

      {hasSources && (
        <div className="message-bubble__citations" data-testid="citations">
          {message.source_references!.map((ref, i) => (
            <button
              key={`${ref.document_id}-${i}`}
              className="citation-badge"
              onClick={() => onSourceClick?.(message.source_references!)}
              aria-label={`Citation: ${ref.file_name}${ref.page_number != null ? `, page ${ref.page_number}` : ''}`}
              data-testid="citation-badge"
            >
              {ref.file_name}
              {ref.page_number != null && ` p.${ref.page_number}`}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
