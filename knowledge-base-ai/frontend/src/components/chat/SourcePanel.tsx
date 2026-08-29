/**
 * SourcePanel — displays document source references for the selected citation.
 *
 * Shown on the right-hand side of ChatView when the user clicks a citation
 * badge on an assistant message (frontend-contract.md §2.1).
 *
 * When `sources` is empty the panel renders a placeholder prompt.
 */
import type { SourceReference } from '../../services/types';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface SourcePanelProps {
  sources: SourceReference[];
  onClose?: () => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function SourcePanel({ sources, onClose }: SourcePanelProps) {
  const isEmpty = sources.length === 0;

  return (
    <aside
      className={`source-panel${isEmpty ? ' source-panel--empty' : ''}`}
      data-testid="source-panel"
      aria-label="Source references"
    >
      {isEmpty ? (
        <p className="source-panel__placeholder" data-testid="source-panel-placeholder">
          Click a citation to view sources
        </p>
      ) : (
        <>
          <div className="source-panel__header">
            <h3 className="source-panel__title">Sources</h3>
            {onClose && (
              <button
                className="source-panel__close"
                onClick={onClose}
                aria-label="Close sources panel"
                data-testid="source-panel-close"
              >
                ×
              </button>
            )}
          </div>

          <ul className="source-panel__list" data-testid="source-panel-list">
            {sources.map((ref, i) => (
              <li
                key={`${ref.document_id}-${i}`}
                className="source-panel__item"
                data-testid="source-panel-item"
              >
                <span className="source-panel__filename">{ref.file_name}</span>

                {ref.page_number != null && (
                  <span className="source-panel__page" data-testid="source-panel-page">
                    Page {ref.page_number}
                  </span>
                )}

                <span className="source-panel__score" data-testid="source-panel-score">
                  {Math.round(ref.relevance_score * 100)}% relevance
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
    </aside>
  );
}
