/**
 * Unit tests for IngestionProgress component.
 */

import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import IngestionProgress from './IngestionProgress';
import type { IngestionJob } from '../../services/types';

function makeJob(overrides: Partial<IngestionJob> = {}): IngestionJob {
  return {
    id: 'job-1',
    source_folder: '/docs',
    trigger_reason: 'user',
    total_files: 10,
    processed_files: 5,
    new_files: 5,
    modified_files: 0,
    deleted_files: 0,
    skipped_files: 0,
    status: 'running',
    error_message: null,
    started_at: new Date(Date.now() - 50000).toISOString(), // 50 seconds ago
    completed_at: null,
    progress_pct: 50,
    ...overrides,
  };
}

describe('IngestionProgress', () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['Date'] });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders running state with current file and ETA', () => {
    const job = makeJob({ status: 'running', processed_files: 5, total_files: 10, progress_pct: 50 });
    // 5 files in 50 seconds = 10s per file. 5 remaining = 50 seconds remaining.
    render(<IngestionProgress job={job} currentFile="guide.pdf" fileErrors={[]} />);
    
    expect(screen.getByText('Ingestion in progress...')).toBeInTheDocument();
    expect(screen.getByText('5 / 10 files')).toBeInTheDocument();
    
    // Process bar length via inline styles (we can't easily assert on style from jsdom sometimes, 
    // but jsdom supports it). However, it's an implementation detail, we can just check DOM if we want.
    // We'll skip the inline style assertion and check current file
    expect(screen.getByText('guide.pdf')).toBeInTheDocument();
    
    // Check ETA (approx 50 seconds)
    expect(screen.getByText('50 sec')).toBeInTheDocument();
  });

  it('shows calculating when processed is 0', () => {
    const job = makeJob({ processed_files: 0 });
    render(<IngestionProgress job={job} currentFile="start.pdf" fileErrors={[]} />);
    expect(screen.getByText('Calculating...')).toBeInTheDocument();
  });

  it('shows calculating when elapsed time is negative', () => {
    const job = makeJob({ started_at: new Date(Date.now() + 5000).toISOString() });
    render(<IngestionProgress job={job} currentFile="start.pdf" fileErrors={[]} />);
    expect(screen.getByText('Calculating...')).toBeInTheDocument();
  });

  it('renders completed state with summary', () => {
    const job = makeJob({
      status: 'completed',
      processed_files: 10,
      new_files: 7,
      modified_files: 1,
      deleted_files: 2,
      skipped_files: 0,
      progress_pct: 100,
    });
    
    render(<IngestionProgress job={job} currentFile={null} fileErrors={[]} />);
    
    expect(screen.getByText('Ingestion completed')).toBeInTheDocument();
    expect(screen.getByText(/Processed: 10/)).toBeInTheDocument();
    expect(screen.getByText(/New: 7/)).toBeInTheDocument();
    expect(screen.getByText(/Modified: 1/)).toBeInTheDocument();
    expect(screen.getByText(/Deleted: 2/)).toBeInTheDocument();
    expect(screen.queryByText('Current:')).not.toBeInTheDocument(); // ETA and current file not shown
  });

  it('renders failed state with global error message', () => {
    const job = makeJob({
      status: 'failed',
      error_message: 'Out of disk space',
    });
    
    render(<IngestionProgress job={job} currentFile={null} fileErrors={[]} />);
    
    expect(screen.getByText('Ingestion failed')).toBeInTheDocument();
    expect(screen.getByText('Out of disk space')).toBeInTheDocument();
  });

  it('renders inline file errors', () => {
    const job = makeJob();
    const fileErrors = [
      { file_name: 'corrupt.pdf', error: 'PDF EOF marker missing' },
      { file_name: 'locked.docx', error: 'Password required' },
    ];
    
    render(<IngestionProgress job={job} currentFile="next.pdf" fileErrors={fileErrors} />);
    
    expect(screen.getByText('File Errors:')).toBeInTheDocument();
    expect(screen.getByText('corrupt.pdf:')).toBeInTheDocument();
    expect(screen.getByText('PDF EOF marker missing')).toBeInTheDocument();
    expect(screen.getByText('locked.docx:')).toBeInTheDocument();
    expect(screen.getByText('Password required')).toBeInTheDocument();
  });
});
