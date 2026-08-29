/**
 * useIngestion — manages an ingestion job lifecycle.
 *
 * Responsibilities:
 *  - Trigger a new ingestion job via POST /ingestion/start
 *  - Open a WebSocket to /api/v1/ingestion/progress/{job_id} for live updates
 *  - Track job status, progress, current file, and per-file errors
 *  - Handle 409 Conflict (job already running)
 *  - Expose a stop / cleanup function for unmount
 *
 * Usage:
 *   const {
 *     job, currentFile, fileErrors,
 *     isRunning, startIngestion,
 *     startError, starting,
 *   } = useIngestion();
 */
import { useState, useCallback, useRef } from 'react';
import { startIngestion as apiStartIngestion, getIngestionStatus } from '../services/api';
import { WebSocketManager } from '../services/websocket';
import type {
  IngestionJob,
  IngestionProgressMessage,
  FileCompleteMessage,
  FileErrorMessage,
  IngestionCompletedMessage,
} from '../services/types';
import type { FileError } from '../components/documents/IngestionProgress';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface UseIngestionResult {
  /** Current job snapshot — null if no job has been started yet. */
  job: IngestionJob | null;
  /** Name of the file currently being processed. */
  currentFile: string | null;
  /** Accumulated per-file errors received via WebSocket. */
  fileErrors: FileError[];
  /** True while the POST /ingestion/start request is in flight. */
  starting: boolean;
  /** Error message from the start request (including 409 conflict text). */
  startError: string | null;
  /** True if the active job has status === 'running'. */
  isRunning: boolean;
  /** Reconnecting indicator (WS lost connection and is retrying). */
  reconnecting: boolean;
  /** Trigger a new ingestion job. Resolves when the job ID is received. */
  startIngestion: (sourceFolder?: string) => Promise<void>;
  /** Disconnect the WebSocket and clear job state. */
  reset: () => void;
}

// ---------------------------------------------------------------------------
// Helper
// ---------------------------------------------------------------------------

function extractMessage(err: unknown): string {
  if (err && typeof err === 'object') {
    const e = err as Record<string, unknown>;
    if (typeof e['message'] === 'string') return e['message'];
  }
  return 'An unexpected error occurred.';
}

function applyProgressMessage(
  prev: IngestionJob,
  msg: IngestionProgressMessage,
): IngestionJob {
  return {
    ...prev,
    processed_files: msg.processed_files,
    total_files: msg.total_files,
    progress_pct: msg.progress_pct,
  };
}

function applyCompletedMessage(
  prev: IngestionJob,
  msg: IngestionCompletedMessage,
): IngestionJob {
  return {
    ...prev,
    status: 'completed',
    total_files: msg.total_files,
    new_files: msg.new_files,
    modified_files: msg.modified_files,
    deleted_files: msg.deleted_files,
    skipped_files: msg.skipped_files,
    processed_files: msg.total_files,
    progress_pct: 100,
    completed_at: new Date().toISOString(),
  };
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useIngestion(): UseIngestionResult {
  const [job, setJob] = useState<IngestionJob | null>(null);
  const [currentFile, setCurrentFile] = useState<string | null>(null);
  const [fileErrors, setFileErrors] = useState<FileError[]>([]);
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);
  const [reconnecting, setReconnecting] = useState(false);

  const wsRef = useRef<WebSocketManager | null>(null);

  // ---------------------------------------------------------------------------
  // WebSocket setup
  // ---------------------------------------------------------------------------

  const connectWs = useCallback((jobId: string) => {
    // Clean up any previous connection
    wsRef.current?.disconnect();

    const ws = new WebSocketManager(`/api/v1/ingestion/progress/${jobId}`);
    wsRef.current = ws;

    ws.onMessage<IngestionProgressMessage>('progress', (msg) => {
      setCurrentFile(msg.current_file);
      setJob((prev) => (prev ? applyProgressMessage(prev, msg) : prev));
      setReconnecting(false);
    });

    ws.onMessage<FileCompleteMessage>('file_complete', (_msg) => {
      // file_complete just confirms the file finished — progress message
      // already updated processed_files, so no extra state needed here.
    });

    ws.onMessage<FileErrorMessage>('file_error', (msg) => {
      setFileErrors((prev) => [...prev, { file_name: msg.file_name, error: msg.error }]);
    });

    ws.onMessage<IngestionCompletedMessage>('completed', (msg) => {
      setJob((prev) => (prev ? applyCompletedMessage(prev, msg) : prev));
      setCurrentFile(null);
      ws.disconnect();
    });

    ws.onMessage<{ type: 'error'; message: string }>('error', (msg) => {
      setJob((prev) =>
        prev
          ? { ...prev, status: 'failed', error_message: msg.message ?? 'Unknown error' }
          : prev,
      );
      ws.disconnect();
    });

    ws.onClose(() => {
      // If job still shows running after WS closes, mark reconnecting
      setJob((prev) => {
        if (prev?.status === 'running') setReconnecting(true);
        return prev;
      });
    });

    ws.onMaxRetries(() => {
      // Gave up reconnecting — fall back to polling final status once
      setReconnecting(false);
      getIngestionStatus(jobId)
        .then((latestJob) => setJob(latestJob))
        .catch(() => {
          setJob((prev) =>
            prev ? { ...prev, status: 'failed', error_message: 'Lost connection to server.' } : prev,
          );
        });
    });

    ws.connect();
  }, []);

  // ---------------------------------------------------------------------------
  // Start ingestion
  // ---------------------------------------------------------------------------

  const startIngestion = useCallback(
    async (sourceFolder?: string): Promise<void> => {
      setStarting(true);
      setStartError(null);
      setFileErrors([]);
      setCurrentFile(null);

      try {
        const { job_id } = await apiStartIngestion(
          sourceFolder ? { source_folder: sourceFolder } : {},
        );

        // Fetch initial job state to populate UI immediately
        const initialJob = await getIngestionStatus(job_id);
        setJob(initialJob);

        connectWs(job_id);
      } catch (err: unknown) {
        setStartError(extractMessage(err));
      } finally {
        setStarting(false);
      }
    },
    [connectWs],
  );

  // ---------------------------------------------------------------------------
  // Reset
  // ---------------------------------------------------------------------------

  const reset = useCallback(() => {
    wsRef.current?.disconnect();
    wsRef.current = null;
    setJob(null);
    setCurrentFile(null);
    setFileErrors([]);
    setStartError(null);
    setReconnecting(false);
  }, []);

  return {
    job,
    currentFile,
    fileErrors,
    starting,
    startError,
    isRunning: job?.status === 'running',
    reconnecting,
    startIngestion,
    reset,
  };
}
