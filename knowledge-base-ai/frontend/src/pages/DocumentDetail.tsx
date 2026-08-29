/**
 * DocumentDetail — document metadata and on-demand summary (frontend-contract.md §8.6).
 *
 * Loads document details via GET /documents/{id}, then renders:
 * - Back navigation
 * - File metadata (name, type, size, chunks, ingested_at)
 * - SummaryView component (generate / display summary)
 */
import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import SummaryView from '../components/documents/SummaryView';
import { getDocument } from '../services/api';
import type { Document } from '../services/types';

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function extractMsg(err: unknown): string {
  if (err && typeof err === 'object') {
    const e = err as Record<string, unknown>;
    if (typeof e['message'] === 'string') return e['message'];
  }
  return 'Failed to load document.';
}

export default function DocumentDetail() {
  const { documentId } = useParams<{ documentId: string }>();
  const navigate = useNavigate();

  const [doc, setDoc] = useState<Document | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [hasSummary, setHasSummary] = useState(false);

  useEffect(() => {
    if (!documentId) return;
    let cancelled = false;

    setLoading(true);
    getDocument(documentId)
      .then((d) => {
        if (!cancelled) {
          setDoc(d);
          setHasSummary(d.has_summary ?? false);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(extractMsg(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [documentId]);

  const handleSummaryGenerated = useCallback(() => setHasSummary(true), []);

  if (loading) {
    return (
      <div data-testid="document-detail-loading" className="page page--document-detail">
        Loading document…
      </div>
    );
  }

  if (error || !doc) {
    return (
      <div data-testid="document-detail-error" className="page page--document-detail">
        <button onClick={() => navigate('/documents')}>← Back to Documents</button>
        <p role="alert">{error ?? 'Document not found.'}</p>
      </div>
    );
  }

  return (
    <div data-testid="document-detail" className="page page--document-detail">
      <button
        data-testid="btn-back"
        className="btn btn--ghost"
        onClick={() => navigate('/documents')}
      >
        ← Back to Documents
      </button>

      <h1 data-testid="document-name">{doc.file_name}</h1>
      <hr />

      <dl data-testid="document-metadata" className="metadata-list">
        <dt>Type</dt>
        <dd data-testid="doc-type">{doc.file_type.toUpperCase()}</dd>

        <dt>Size</dt>
        <dd data-testid="doc-size">{formatBytes(doc.file_size_bytes)}</dd>

        <dt>Chunks</dt>
        <dd data-testid="doc-chunks">{doc.chunk_count}</dd>

        {doc.ingested_at && (
          <>
            <dt>Ingested</dt>
            <dd data-testid="doc-ingested-at">{formatDate(doc.ingested_at)}</dd>
          </>
        )}
      </dl>

      <SummaryView
        documentId={doc.id}
        hasSummary={hasSummary}
        onSummaryGenerated={handleSummaryGenerated}
      />
    </div>
  );
}

