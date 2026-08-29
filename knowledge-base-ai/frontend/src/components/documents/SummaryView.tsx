/**
 * SummaryView — displays a document summary with section references.
 *
 * Behaviors (frontend-contract.md §8.6):
 * - If `hasSummary=true`: loads cached summary via GET /documents/{id}/summary
 * - "Regenerate" button: calls POST /documents/{id}/summary, shows loader
 * - "Generate Summary" button when no summary exists: same POST flow
 * - Error: inline alert with "Try again" button
 */
import { useCallback, useEffect, useState } from 'react';
import { generateSummary, getSummary } from '../../services/api';
import type { DocumentSummary } from '../../services/types';

export interface SummaryViewProps {
  documentId: string;
  /** Whether a summary already exists (from `Document.has_summary`). */
  hasSummary: boolean;
  /** Called after a summary is successfully generated (new or regen). */
  onSummaryGenerated?: () => void;
}

function extractMsg(err: unknown): string {
  if (err && typeof err === 'object') {
    const e = err as Record<string, unknown>;
    if (typeof e['message'] === 'string') return e['message'];
  }
  return 'An unexpected error occurred.';
}

export default function SummaryView({
  documentId,
  hasSummary,
  onSummaryGenerated,
}: SummaryViewProps) {
  const [summary, setSummary] = useState<DocumentSummary | null>(null);
  const [generating, setGenerating] = useState(false);
  const [fetchLoading, setFetchLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load cached summary when the component mounts (if one exists)
  useEffect(() => {
    if (!hasSummary) return;
    let cancelled = false;

    setFetchLoading(true);
    getSummary(documentId)
      .then((data) => {
        if (!cancelled) setSummary(data);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(extractMsg(err));
      })
      .finally(() => {
        if (!cancelled) setFetchLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [documentId, hasSummary]);

  const handleGenerate = useCallback(async () => {
    setGenerating(true);
    setError(null);
    try {
      const result = await generateSummary(documentId);
      setSummary(result);
      onSummaryGenerated?.();
    } catch (err: unknown) {
      setError(extractMsg(err));
    } finally {
      setGenerating(false);
    }
  }, [documentId, onSummaryGenerated]);

  // Loading state — fetching cached summary or generating
  if (fetchLoading || (generating && !summary)) {
    return (
      <div data-testid="summary-loading" className="summary-loading" aria-live="polite">
        <span className="spinner" aria-hidden="true" />
        {generating ? 'Generating summary…' : 'Loading summary…'}
      </div>
    );
  }

  // Summary exists (cached or freshly generated)
  if (summary) {
    return (
      <div data-testid="summary-view" className="summary-view">
        <div className="summary-header">
          <h2>Summary</h2>
          <button
            data-testid="btn-regenerate"
            className="btn btn--secondary"
            onClick={() => { void handleGenerate(); }}
            disabled={generating}
            aria-label="Regenerate summary"
          >
            {generating ? 'Regenerating…' : '↻ Regenerate'}
          </button>
        </div>

        <p data-testid="summary-text" className="summary-text">
          {summary.summary_text}
        </p>

        {summary.section_references && summary.section_references.length > 0 && (
          <div data-testid="section-references" className="section-references">
            <h3>Sections referenced:</h3>
            <ul>
              {summary.section_references.map((ref, i) => (
                <li key={i} data-testid="section-reference-item">
                  <strong>{ref.section}</strong>
                  {ref.page !== null && ref.page !== undefined && ` (p. ${ref.page})`}
                  {ref.contribution && ` — ${ref.contribution}`}
                </li>
              ))}
            </ul>
          </div>
        )}

        {error && (
          <p data-testid="summary-error" role="alert" className="inline-error">
            {error}{' '}
            <button onClick={() => { void handleGenerate(); }} aria-label="Retry summary generation">
              Try again
            </button>
          </p>
        )}
      </div>
    );
  }

  // No summary yet
  return (
    <div data-testid="summary-empty" className="summary-empty">
      {error && (
        <p data-testid="summary-error" role="alert" className="inline-error">
          Summary generation failed: {error}{' '}
          <button onClick={() => { void handleGenerate(); }} aria-label="Retry summary generation">
            Try again
          </button>
        </p>
      )}
      <p>No summary generated yet.</p>
      <button
        data-testid="btn-generate"
        className="btn btn--primary"
        onClick={() => { void handleGenerate(); }}
        disabled={generating}
      >
        {generating ? 'Generating…' : 'Generate Summary'}
      </button>
    </div>
  );
}
