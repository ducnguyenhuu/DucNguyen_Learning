/**
 * DocumentTable — sortable table of ingested documents.
 *
 * Columns: Name · Type · Chunks · Actions (Summary + Delete)
 *
 * Props
 * -----
 * documents        — list of Document objects to render
 * onDelete         — async callback invoked after the user confirms deletion;
 *                    the parent is responsible for removing the row from state
 * onGenerateSummary — callback invoked when the Summary button is clicked
 *
 * Behaviour (per frontend-contract.md §2.2 and §8.2):
 *  - Click document name       → navigate to /documents/:id
 *  - Click column header       → sort asc/desc (name, type, chunks)
 *  - Click 🗑                  → open inline confirmation dialog
 *  - Confirm delete            → call onDelete(id); show success notice
 *  - Cancel                    → close dialog
 *  - Empty list                → "No documents found" row
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import type { Document } from '../../services/types';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type SortColumn = 'file_name' | 'file_type' | 'chunk_count';
type SortDir = 'asc' | 'desc';

export interface DocumentTableProps {
  documents: Document[];
  onDelete: (id: string) => Promise<void>;
  onGenerateSummary: (id: string) => void;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function sortDocs(docs: Document[], col: SortColumn, dir: SortDir): Document[] {
  return [...docs].sort((a, b) => {
    const av = a[col];
    const bv = b[col];
    let cmp = 0;
    if (typeof av === 'number' && typeof bv === 'number') {
      cmp = av - bv;
    } else {
      cmp = String(av).localeCompare(String(bv));
    }
    return dir === 'asc' ? cmp : -cmp;
  });
}

function fileTypeLabel(ft: string): string {
  return ft.toUpperCase();
}

// ---------------------------------------------------------------------------
// Sub-component: Confirmation dialog
// ---------------------------------------------------------------------------

interface ConfirmDialogProps {
  fileName: string;
  deleting: boolean;
  error: string | null;
  onConfirm: () => void;
  onCancel: () => void;
}

function ConfirmDialog({ fileName, deleting, error, onConfirm, onCancel }: ConfirmDialogProps) {
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="delete-dialog-title"
      className="doc-table__dialog-overlay"
    >
      <div className="doc-table__dialog">
        <h2 id="delete-dialog-title" className="doc-table__dialog-title">
          Delete document?
        </h2>
        <p className="doc-table__dialog-body">
          Delete <strong>{fileName}</strong>? This will remove the document and all its indexed
          chunks. This cannot be undone.
        </p>
        {error && (
          <p role="alert" className="doc-table__dialog-error">
            {error}
          </p>
        )}
        <div className="doc-table__dialog-actions">
          <button
            type="button"
            className="btn btn--secondary"
            onClick={onCancel}
            disabled={deleting}
          >
            Cancel
          </button>
          <button
            type="button"
            className="btn btn--danger"
            onClick={onConfirm}
            disabled={deleting}
            aria-busy={deleting}
          >
            {deleting ? 'Deleting…' : 'Delete'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function DocumentTable({
  documents,
  onDelete,
  onGenerateSummary,
}: DocumentTableProps) {
  const navigate = useNavigate();

  // Sort state
  const [sortCol, setSortCol] = useState<SortColumn>('file_name');
  const [sortDir, setSortDir] = useState<SortDir>('asc');

  // Delete dialog state
  const [pendingDelete, setPendingDelete] = useState<Document | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // ── Sort helpers ──────────────────────────────────────────────────────────

  function handleSort(col: SortColumn) {
    if (col === sortCol) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortCol(col);
      setSortDir('asc');
    }
  }

  function sortIndicator(col: SortColumn): string {
    if (col !== sortCol) return '';
    return sortDir === 'asc' ? ' ▲' : ' ▼';
  }

  // ── Delete flow ───────────────────────────────────────────────────────────

  function handleDeleteClick(doc: Document) {
    setDeleteError(null);
    setSuccessMsg(null);
    setPendingDelete(doc);
  }

  async function handleDeleteConfirm() {
    if (!pendingDelete) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      await onDelete(pendingDelete.id);
      setSuccessMsg(`"${pendingDelete.file_name}" deleted successfully.`);
      setPendingDelete(null);
    } catch (err: unknown) {
      const msg =
        err && typeof err === 'object' && 'message' in err
          ? String((err as { message: string }).message)
          : 'Failed to delete document. Please try again.';
      setDeleteError(msg);
    } finally {
      setDeleting(false);
    }
  }

  function handleDeleteCancel() {
    setPendingDelete(null);
    setDeleteError(null);
  }

  // ── Render ────────────────────────────────────────────────────────────────

  const sorted = sortDocs(documents, sortCol, sortDir);

  return (
    <div className="doc-table-wrapper">
      {successMsg && (
        <div role="status" aria-live="polite" className="doc-table__toast doc-table__toast--success">
          {successMsg}
        </div>
      )}

      <table className="doc-table" aria-label="Ingested documents">
        <thead>
          <tr>
            <th scope="col">
              <button
                type="button"
                className="doc-table__sort-btn"
                onClick={() => handleSort('file_name')}
                aria-label={`Sort by Name${sortIndicator('file_name')}`}
              >
                Name{sortIndicator('file_name')}
              </button>
            </th>
            <th scope="col">
              <button
                type="button"
                className="doc-table__sort-btn"
                onClick={() => handleSort('file_type')}
                aria-label={`Sort by Type${sortIndicator('file_type')}`}
              >
                Type{sortIndicator('file_type')}
              </button>
            </th>
            <th scope="col">
              <button
                type="button"
                className="doc-table__sort-btn"
                onClick={() => handleSort('chunk_count')}
                aria-label={`Sort by Chunks${sortIndicator('chunk_count')}`}
              >
                Chunks{sortIndicator('chunk_count')}
              </button>
            </th>
            <th scope="col">Actions</th>
          </tr>
        </thead>
        <tbody>
          {sorted.length === 0 ? (
            <tr>
              <td colSpan={4} className="doc-table__empty">
                No documents found.
              </td>
            </tr>
          ) : (
            sorted.map((doc) => (
              <tr key={doc.id} className="doc-table__row">
                <td>
                  <button
                    type="button"
                    className="doc-table__name-btn"
                    onClick={() => navigate(`/documents/${doc.id}`)}
                  >
                    {doc.file_name}
                  </button>
                </td>
                <td>{fileTypeLabel(doc.file_type)}</td>
                <td>{doc.chunk_count}</td>
                <td className="doc-table__actions">
                  <button
                    type="button"
                    className="btn btn--icon"
                    title="Generate / view summary"
                    aria-label={`Generate summary for ${doc.file_name}`}
                    onClick={() => onGenerateSummary(doc.id)}
                  >
                    📄 Summary
                  </button>
                  <button
                    type="button"
                    className="btn btn--icon btn--danger-ghost"
                    title="Delete document"
                    aria-label={`Delete ${doc.file_name}`}
                    onClick={() => handleDeleteClick(doc)}
                  >
                    🗑
                  </button>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>

      {pendingDelete && (
        <ConfirmDialog
          fileName={pendingDelete.file_name}
          deleting={deleting}
          error={deleteError}
          onConfirm={() => { void handleDeleteConfirm(); }}
          onCancel={handleDeleteCancel}
        />
      )}
    </div>
  );
}
