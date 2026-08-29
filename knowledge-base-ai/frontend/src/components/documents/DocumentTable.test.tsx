/**
 * Unit tests for DocumentTable component.
 *
 * Covers (per frontend-contract.md §2.2 and §8.2):
 *  - Table renders document rows with correct columns
 *  - Empty state when no documents
 *  - Sorting columns (name, type, chunk_count) asc/desc toggle
 *  - Clicking document name navigates to /documents/:id
 *  - Summary button calls onGenerateSummary callback
 *  - Delete button opens confirmation dialog
 *  - Cancel hides the dialog
 *  - Confirm calls onDelete; success message shown
 *  - onDelete rejection shows error inside dialog
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import DocumentTable from './DocumentTable';
import type { DocumentTableProps } from './DocumentTable';
import type { Document } from '../../services/types';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const mockNavigate = vi.fn();

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

function makeDoc(overrides: Partial<Document> = {}): Document {
  return {
    id: 'doc-1',
    file_name: 'guide.pdf',
    file_type: 'pdf',
    file_path: '/docs/guide.pdf',
    file_hash: 'abc',
    file_size_bytes: 1048576,
    chunk_count: 42,
    status: 'completed',
    error_message: null,
    ingested_at: '2026-03-05T12:00:00',
    created_at: '2026-03-05T11:00:00',
    updated_at: '2026-03-05T12:00:00',
    ...overrides,
  };
}

function renderTable(props: Partial<DocumentTableProps> & { documents: Document[] }) {
  const onDelete = props.onDelete ?? vi.fn().mockResolvedValue(undefined);
  const onGenerateSummary = props.onGenerateSummary ?? vi.fn();
  const result = render(
    <MemoryRouter>
      <DocumentTable
        documents={props.documents}
        onDelete={onDelete}
        onGenerateSummary={onGenerateSummary}
      />
    </MemoryRouter>,
  );
  return { ...result, onDelete, onGenerateSummary };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

beforeEach(() => {
  mockNavigate.mockReset();
});

describe('DocumentTable — rendering', () => {
  it('renders column headers', () => {
    renderTable({ documents: [] });
    expect(screen.getByRole('button', { name: /sort by name/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /sort by type/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /sort by chunks/i })).toBeInTheDocument();
    expect(screen.getByText('Actions')).toBeInTheDocument();
  });

  it('shows empty state when no documents', () => {
    renderTable({ documents: [] });
    expect(screen.getByText(/no documents found/i)).toBeInTheDocument();
  });

  it('renders a row for each document', () => {
    const docs = [makeDoc({ id: 'd1', file_name: 'a.pdf' }), makeDoc({ id: 'd2', file_name: 'b.md' })];
    renderTable({ documents: docs });
    expect(screen.getByRole('button', { name: 'a.pdf' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'b.md' })).toBeInTheDocument();
  });

  it('renders file type in uppercase', () => {
    renderTable({ documents: [makeDoc({ file_type: 'pdf' })] });
    expect(screen.getByText('PDF')).toBeInTheDocument();
  });

  it('renders chunk count', () => {
    renderTable({ documents: [makeDoc({ chunk_count: 99 })] });
    expect(screen.getByText('99')).toBeInTheDocument();
  });
});

describe('DocumentTable — sorting', () => {
  const docs = [
    makeDoc({ id: 'd1', file_name: 'zebra.pdf', file_type: 'pdf', chunk_count: 5 }),
    makeDoc({ id: 'd2', file_name: 'alpha.md', file_type: 'md', chunk_count: 20 }),
    makeDoc({ id: 'd3', file_name: 'middle.docx', file_type: 'docx', chunk_count: 10 }),
  ];

  it('defaults to ascending sort by name', () => {
    renderTable({ documents: docs });
    const rows = screen.getAllByRole('row').slice(1); // skip header
    expect(rows[0]).toHaveTextContent('alpha.md');
    expect(rows[2]).toHaveTextContent('zebra.pdf');
  });

  it('toggles to descending when Name header clicked again', () => {
    renderTable({ documents: docs });
    // Initial = asc. Click once to go desc.
    fireEvent.click(screen.getByRole('button', { name: /sort by name/i }));
    const rows = screen.getAllByRole('row').slice(1);
    expect(rows[0]).toHaveTextContent('zebra.pdf');
    expect(rows[2]).toHaveTextContent('alpha.md');
  });

  it('sorts by chunk_count ascending when Chunks header clicked', () => {
    renderTable({ documents: docs });
    fireEvent.click(screen.getByRole('button', { name: /sort by chunks/i }));
    const rows = screen.getAllByRole('row').slice(1);
    expect(rows[0]).toHaveTextContent('zebra.pdf'); // chunk_count 5
    expect(rows[2]).toHaveTextContent('alpha.md');  // chunk_count 20
  });

  it('toggles chunks sort to descending on second click', () => {
    renderTable({ documents: docs });
    fireEvent.click(screen.getByRole('button', { name: /sort by chunks/i }));
    fireEvent.click(screen.getByRole('button', { name: /sort by chunks/i }));
    const rows = screen.getAllByRole('row').slice(1);
    expect(rows[0]).toHaveTextContent('alpha.md'); // chunk_count 20
  });

  it('sorts by type when Type header clicked', () => {
    renderTable({ documents: docs });
    fireEvent.click(screen.getByRole('button', { name: /sort by type/i }));
    const rows = screen.getAllByRole('row').slice(1);
    // docx < md < pdf alphabetically
    expect(rows[0]).toHaveTextContent('middle.docx');
    expect(rows[2]).toHaveTextContent('zebra.pdf');
  });
});

describe('DocumentTable — navigation', () => {
  it('navigates to /documents/:id when name button clicked', () => {
    renderTable({ documents: [makeDoc({ id: 'abc123', file_name: 'my-file.pdf' })] });
    fireEvent.click(screen.getByRole('button', { name: 'my-file.pdf' }));
    expect(mockNavigate).toHaveBeenCalledWith('/documents/abc123');
  });
});

describe('DocumentTable — summary button', () => {
  it('calls onGenerateSummary with document id', () => {
    const onGenerateSummary = vi.fn();
    renderTable({
      documents: [makeDoc({ id: 'sum-1', file_name: 'doc.pdf' })],
      onGenerateSummary,
    });
    fireEvent.click(screen.getByRole('button', { name: /generate summary for doc\.pdf/i }));
    expect(onGenerateSummary).toHaveBeenCalledWith('sum-1');
  });
});

describe('DocumentTable — delete flow', () => {
  it('shows confirmation dialog when delete button clicked', () => {
    renderTable({ documents: [makeDoc({ file_name: 'target.pdf' })] });
    fireEvent.click(screen.getByRole('button', { name: /delete target\.pdf/i }));
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    // filename appears in the dialog body (inside <strong>)
    expect(screen.getByRole('dialog')).toHaveTextContent('target.pdf');
  });

  it('hides dialog when Cancel clicked', () => {
    renderTable({ documents: [makeDoc({ file_name: 'target.pdf' })] });
    fireEvent.click(screen.getByRole('button', { name: /delete target\.pdf/i }));
    fireEvent.click(screen.getByRole('button', { name: /cancel/i }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('calls onDelete with document id when Delete confirmed', async () => {
    const onDelete = vi.fn().mockResolvedValue(undefined);
    renderTable({ documents: [makeDoc({ id: 'del-id', file_name: 'bye.pdf' })], onDelete });
    fireEvent.click(screen.getByRole('button', { name: /delete bye\.pdf/i }));
    fireEvent.click(screen.getByRole('button', { name: /^delete$/i }));
    await waitFor(() => expect(onDelete).toHaveBeenCalledWith('del-id'));
  });

  it('shows success message after deletion', async () => {
    const onDelete = vi.fn().mockResolvedValue(undefined);
    renderTable({ documents: [makeDoc({ file_name: 'removed.pdf' })], onDelete });
    fireEvent.click(screen.getByRole('button', { name: /delete removed\.pdf/i }));
    fireEvent.click(screen.getByRole('button', { name: /^delete$/i }));
    await waitFor(() =>
      expect(screen.getByRole('status')).toHaveTextContent(/removed\.pdf.*deleted/i),
    );
  });

  it('hides dialog after successful deletion', async () => {
    const onDelete = vi.fn().mockResolvedValue(undefined);
    renderTable({ documents: [makeDoc({ file_name: 'gone.pdf' })], onDelete });
    fireEvent.click(screen.getByRole('button', { name: /delete gone\.pdf/i }));
    fireEvent.click(screen.getByRole('button', { name: /^delete$/i }));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  });

  it('shows error inside dialog when onDelete rejects', async () => {
    const onDelete = vi.fn().mockRejectedValue({ message: 'Document not found' });
    renderTable({ documents: [makeDoc({ file_name: 'err.pdf' })], onDelete });
    fireEvent.click(screen.getByRole('button', { name: /delete err\.pdf/i }));
    fireEvent.click(screen.getByRole('button', { name: /^delete$/i }));
    await waitFor(() =>
      expect(screen.getByRole('alert')).toHaveTextContent('Document not found'),
    );
    // Dialog stays open on error
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });
});
