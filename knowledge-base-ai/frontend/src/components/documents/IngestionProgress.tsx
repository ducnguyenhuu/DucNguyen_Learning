/**
 * IngestionProgress — displays ongoing or recently completed ingestion job status.
 *
 * Requirements (frontend-contract.md §2.2):
 * - Progress bar (pct width)
 * - Processed / total files count
 * - Current file name
 * - Estimated time remaining
 * - Inline file errors (from FileErrorMessage stream)
 */
import { useMemo } from 'react';
import type { IngestionJob } from '../../services/types';

export interface FileError {
  file_name: string;
  error: string;
}

export interface IngestionProgressProps {
  job: IngestionJob;
  currentFile: string | null;
  fileErrors: FileError[];
}

// ---------------------------------------------------------------------------
// Formatters
// ---------------------------------------------------------------------------

function formatEta(startedAtStr: string, processed: number, total: number): string {
  if (processed === 0 || total === 0 || processed >= total) return 'Calculating...';

  const startedAt = new Date(startedAtStr).getTime();
  const now = Date.now();
  const elapsedMs = now - startedAt;

  // If elapsed time is negative or impossible (due to clock skew)
  if (elapsedMs < 0) return 'Calculating...';

  const timePerFile = elapsedMs / processed;
  const remainingFiles = total - processed;
  const remainingMs = remainingFiles * timePerFile;

  if (remainingMs < 1000) return '< 1 sec';
  if (remainingMs < 60000) return `${Math.ceil(remainingMs / 1000)} sec`;

  const mins = Math.floor(remainingMs / 60000);
  const secs = Math.ceil((remainingMs % 60000) / 1000);
  
  if (mins > 60) {
    const hrs = Math.floor(mins / 60);
    const remMins = mins % 60;
    return `${hrs} hr ${remMins} min`;
  }
  
  return `${mins} min ${secs} sec`;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function IngestionProgress({ job, currentFile, fileErrors }: IngestionProgressProps) {
  const isRunning = job.status === 'running';
  const isFailed = job.status === 'failed';
  const isCompleted = job.status === 'completed';

  // ETA calculation memoised. Note: in a real app, you might want to force tick
  // this so elapsedMs updates even if `processed` doesn't change, but usually
  // files process fast enough or the parent hook forces updates.
  const eta = useMemo(() => {
    if (!isRunning) return null;
    return formatEta(job.started_at, job.processed_files, job.total_files);
  }, [isRunning, job.started_at, job.processed_files, job.total_files]);

  return (
    <div
      className={`ingestion-progress ingestion-progress--${job.status}`}
      role="region"
      aria-labelledby="ingestion-progress-title"
      aria-live={isRunning ? 'polite' : 'off'}
    >
      <div className="ingestion-progress__header">
        <h3 id="ingestion-progress-title" className="ingestion-progress__title">
          {isRunning && 'Ingestion in progress...'}
          {isCompleted && 'Ingestion completed'}
          {isFailed && 'Ingestion failed'}
        </h3>
        <span className="ingestion-progress__counts">
          {job.processed_files} / {job.total_files} files
        </span>
      </div>

      <div className="ingestion-progress__bar-bg" aria-hidden="true">
        <div
          className={`ingestion-progress__bar-fill ingestion-progress__bar-fill--${job.status}`}
          style={{ width: `${job.progress_pct}%` }}
        />
      </div>

      {isRunning && (
        <div className="ingestion-progress__details">
          <div className="ingestion-progress__current">
            <span className="ingestion-progress__label">Current: </span>
            <span className="ingestion-progress__value">{currentFile || '...'}</span>
          </div>
          <div className="ingestion-progress__eta">
            <span className="ingestion-progress__label">Est. remaining: </span>
            <span className="ingestion-progress__value">{eta}</span>
          </div>
        </div>
      )}

      {isCompleted && (
        <div className="ingestion-progress__summary">
          <p>
            Processed: {job.processed_files}. New: {job.new_files}, Modified: {job.modified_files},
            Deleted: {job.deleted_files}, Skipped: {job.skipped_files}
          </p>
        </div>
      )}

      {job.error_message && (
        <div className="ingestion-progress__global-error" role="alert">
          <strong>Error:</strong> {job.error_message}
        </div>
      )}

      {fileErrors.length > 0 && (
        <div className="ingestion-progress__file-errors">
          <h4 className="ingestion-progress__file-errors-title">File Errors:</h4>
          <ul className="ingestion-progress__file-errors-list">
            {fileErrors.map((fe, idx) => (
              <li key={`${fe.file_name}-${idx}`} className="ingestion-progress__file-error-item">
                <span className="ingestion-progress__error-file">{fe.file_name}:</span>{' '}
                <span className="ingestion-progress__error-msg">{fe.error}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
