/**
 * DocumentList — Browse ingested documents and trigger ingestion.
 *
 * Layout (frontend-contract.md §2.2):
 *  - Header row: "Documents" heading + "Run Ingest" button
 *  - IngestionProgress card while a job is active or just completed
 *  - Skeleton table rows while the document list is loading
 *  - Empty state with CTA when no documents have been ingested
 *  - DocumentTable once documents are available
 *
 * Interactions:
 *  - "Run Ingest" → POST /ingestion/start (disabled + "Ingesting…" while running)
 *  - 409 Conflict or other errors → inline alert banner
 *  - Delete document → optimistic removal via useDocuments.deleteDocument
 *  - Summary button / row click → navigate to DocumentDetail (summary generated there)
 *  - Ingestion completed → auto-refresh document list
 */

import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import DocumentTable from '../components/documents/DocumentTable';
import IngestionProgress from '../components/documents/IngestionProgress';
import LoadingSpinner from '../components/common/LoadingSpinner';
import { useDocuments } from '../hooks/useDocuments';
import { useIngestion } from '../hooks/useIngestion';

// ---------------------------------------------------------------------------
// Skeleton loader — 5 animated rows while documents are fetching
// ---------------------------------------------------------------------------

function SkeletonRows() {
  return (
    <div
      className="doc-list__skeleton"
      aria-label="Loading documents"
      aria-busy="true"
      role="status"
    >
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="doc-list__skeleton-row" />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page component
// ---------------------------------------------------------------------------

export default function DocumentList() {
  const navigate = useNavigate();

  // Document list state
  const {
    documents,
    loading,
    error: fetchError,
    deleting,
    deleteDocument,
    refresh,
  } = useDocuments();

  // Ingestion job state
  const {
    job,
    currentFile,
    fileErrors,
    starting,
    startError,
    isRunning,
    startIngestion,
  } = useIngestion();

  // Auto-refresh documents after ingestion completes
  useEffect(() => {
    if (job?.status === 'completed') {
      refresh();
    }
  }, [job?.status, refresh]);

  // Navigate to detail page — summary is generated there (§8.2)
  function handleGenerateSummary(id: string) {
    navigate(`/documents/${id}`);
  }

  const isEmpty = !loading && documents.length === 0 && job === null;
  const ingestLabel = starting ? 'Starting…' : isRunning ? 'Ingesting…' : '▶ Run Ingest';
  const ingestDisabled = starting || isRunning || deleting;

  return (
    <div className="page page--documents">
      {/* ── Header ──────────────────────────────────────────────── */}
      <div className="doc-list__header">
        <h1>Documents</h1>
        <button
          className="btn btn--primary"
          onClick={() => void startIngestion()}
          disabled={ingestDisabled}
          aria-busy={ingestDisabled}
        >
          {ingestLabel}
        </button>
      </div>

      {/* ── Ingestion start-error / fetch-error alerts ───────── */}
      {startError && (
        <div role="alert" className="doc-list__alert doc-list__alert--error">
          {startError}
        </div>
      )}
      {fetchError && !startError && (
        <div role="alert" className="doc-list__alert doc-list__alert--error">
          {fetchError}
        </div>
      )}

      {/* ── Ingestion progress card ───────────────────────────── */}
      {job !== null && (
        <IngestionProgress
          job={job}
          currentFile={currentFile}
          fileErrors={fileErrors}
        />
      )}

      {/* ── Loading state ─────────────────────────────────────── */}
      {loading && documents.length === 0 && <SkeletonRows />}

      {/* ── Empty state ───────────────────────────────────────── */}
      {isEmpty && !loading && (
        <div className="doc-list__empty">
          <div className="doc-list__empty-icon" aria-hidden="true">📂</div>
          <p className="doc-list__empty-heading">No documents yet</p>
          <p className="doc-list__empty-subtext">Run Ingest to get started</p>
          <button
            className="btn btn--primary"
            onClick={() => void startIngestion()}
            disabled={ingestDisabled}
          >
            {ingestLabel}
          </button>
        </div>
      )}

      {/* ── Document table ────────────────────────────────────── */}
      {documents.length > 0 && (
        <DocumentTable
          documents={documents}
          onDelete={deleteDocument}
          onGenerateSummary={handleGenerateSummary}
        />
      )}

      {/* ── Refreshing indicator (stale data re-fetch) ────────── */}
      {loading && documents.length > 0 && (
        <div role="status" aria-live="polite" className="doc-list__refreshing">
          <LoadingSpinner />
          <span>Refreshing…</span>
        </div>
      )}
    </div>
  );
}
