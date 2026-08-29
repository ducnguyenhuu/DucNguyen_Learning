/**
 * Unit tests for SourcePanel component.
 *
 * Covers:
 *  - Empty state shows placeholder text
 *  - Renders one item per source reference
 *  - Displays file name for each source
 *  - Displays page number when present
 *  - Omits page number element when page_number is null
 *  - Displays relevance score as a percentage
 *  - Close button calls onClose
 *  - Close button not rendered when onClose is not provided
 *  - aria-label is present on the aside
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { SourcePanel } from './SourcePanel';
import type { SourceReference } from '../../services/types';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

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
// Empty state
// ---------------------------------------------------------------------------

describe('SourcePanel — empty state', () => {
  it('renders placeholder text when sources array is empty', () => {
    render(<SourcePanel sources={[]} />);
    expect(screen.getByTestId('source-panel-placeholder')).toBeInTheDocument();
  });

  it('applies source-panel--empty class when sources is empty', () => {
    const { container } = render(<SourcePanel sources={[]} />);
    expect(container.querySelector('.source-panel--empty')).not.toBeNull();
  });

  it('does not render the source list when empty', () => {
    render(<SourcePanel sources={[]} />);
    expect(screen.queryByTestId('source-panel-list')).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Populated state
// ---------------------------------------------------------------------------

describe('SourcePanel — populated state', () => {
  it('renders one list item per source reference', () => {
    const refs = [makeRef({ file_name: 'a.pdf' }), makeRef({ file_name: 'b.pdf' })];
    render(<SourcePanel sources={refs} />);
    expect(screen.getAllByTestId('source-panel-item')).toHaveLength(2);
  });

  it('displays file name for each source', () => {
    render(<SourcePanel sources={[makeRef({ file_name: 'architecture.pdf' })]} />);
    expect(screen.getByText('architecture.pdf')).toBeInTheDocument();
  });

  it('displays page number when page_number is present', () => {
    render(<SourcePanel sources={[makeRef({ page_number: 7 })]} />);
    expect(screen.getByTestId('source-panel-page')).toHaveTextContent('Page 7');
  });

  it('omits page element when page_number is null', () => {
    render(<SourcePanel sources={[makeRef({ page_number: null })]} />);
    expect(screen.queryByTestId('source-panel-page')).toBeNull();
  });

  it('displays relevance score as whole-number percentage', () => {
    render(<SourcePanel sources={[makeRef({ relevance_score: 0.91 })]} />);
    expect(screen.getByTestId('source-panel-score')).toHaveTextContent('91% relevance');
  });

  it('rounds relevance score correctly', () => {
    render(<SourcePanel sources={[makeRef({ relevance_score: 0.856 })]} />);
    expect(screen.getByTestId('source-panel-score')).toHaveTextContent('86% relevance');
  });

  it('renders the source list', () => {
    render(<SourcePanel sources={[makeRef()]} />);
    expect(screen.getByTestId('source-panel-list')).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Close button
// ---------------------------------------------------------------------------

describe('SourcePanel — close button', () => {
  it('calls onClose when close button is clicked', () => {
    const onClose = vi.fn();
    render(<SourcePanel sources={[makeRef()]} onClose={onClose} />);
    fireEvent.click(screen.getByTestId('source-panel-close'));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('does not render close button when onClose is not provided', () => {
    render(<SourcePanel sources={[makeRef()]} />);
    expect(screen.queryByTestId('source-panel-close')).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Accessibility
// ---------------------------------------------------------------------------

describe('SourcePanel — accessibility', () => {
  it('has aria-label on the aside element', () => {
    render(<SourcePanel sources={[]} />);
    expect(screen.getByRole('complementary', { name: 'Source references' })).toBeInTheDocument();
  });
});
