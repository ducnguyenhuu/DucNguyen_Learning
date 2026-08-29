/**
 * Unit tests for useIngestion hook.
 *
 * Covers:
 *  - startIngestion calls API + fetches initial job status
 *  - starting=true during request, false after
 *  - 409 / error response sets startError
 *  - WS progress message updates job + currentFile
 *  - WS file_error accumulates fileErrors array
 *  - WS completed message marks job completed
 *  - WS error message marks job failed
 *  - reset() clears state and disconnects WS
 *  - isRunning reflects job.status
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { useIngestion } from './useIngestion';
import * as api from '../services/api';

// ---------------------------------------------------------------------------
// Mock WebSocketManager — defined via vi.hoisted so it exists before vi.mock
// ---------------------------------------------------------------------------

type Handler = (data: unknown) => void;

const { MockWebSocketManager } = vi.hoisted(() => {
  class MockWebSocketManager {
    private handlers: Map<string, Handler[]> = new Map();
    static lastInstance: MockWebSocketManager | null = null;

    constructor() {
      MockWebSocketManager.lastInstance = this;
    }

    connect = vi.fn();
    disconnect = vi.fn();
    send = vi.fn();

    onMessage<T>(type: string, handler: (data: T) => void): () => void {
      const list = this.handlers.get(type) ?? [];
      list.push(handler as Handler);
      this.handlers.set(type, list);
      return () => {};
    }

    onClose(handler: Handler) { return this.onMessage('__close', handler); }
    onMaxRetries(handler: Handler) { return this.onMessage('__max_retries', handler); }

    emit(type: string, data: unknown) {
      const list = this.handlers.get(type) ?? [];
      list.forEach((h) => h(data));
    }
  }

  return { MockWebSocketManager };
});

vi.mock('../services/websocket', () => ({
  WebSocketManager: MockWebSocketManager,
}));

// ---------------------------------------------------------------------------
// Mock API
// ---------------------------------------------------------------------------

vi.mock('../services/api', () => ({
  startIngestion: vi.fn(),
  getIngestionStatus: vi.fn(),
}));

const mockStart = vi.mocked(api.startIngestion);
const mockStatus = vi.mocked(api.getIngestionStatus);

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function makeJob(overrides = {}) {
  return {
    id: 'job-1',
    source_folder: '/docs',
    trigger_reason: 'user' as const,
    total_files: 10,
    processed_files: 0,
    new_files: 0,
    modified_files: 0,
    deleted_files: 0,
    skipped_files: 0,
    status: 'running' as const,
    error_message: null,
    started_at: new Date().toISOString(),
    completed_at: null,
    progress_pct: 0,
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.clearAllMocks();
  MockWebSocketManager.lastInstance = null;
});

afterEach(() => {
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('useIngestion — startIngestion happy path', () => {
  it('calls startIngestion API then fetches initial job status', async () => {
    mockStart.mockResolvedValue({ job_id: 'job-1', message: 'started' });
    mockStatus.mockResolvedValue(makeJob());

    const { result } = renderHook(() => useIngestion());
    await act(async () => {
      await result.current.startIngestion();
    });

    expect(mockStart).toHaveBeenCalledWith({});
    expect(mockStatus).toHaveBeenCalledWith('job-1');
  });

  it('passes source_folder when provided', async () => {
    mockStart.mockResolvedValue({ job_id: 'job-1', message: 'started' });
    mockStatus.mockResolvedValue(makeJob());

    const { result } = renderHook(() => useIngestion());
    await act(async () => {
      await result.current.startIngestion('/custom/path');
    });

    expect(mockStart).toHaveBeenCalledWith({ source_folder: '/custom/path' });
  });

  it('populates job after start', async () => {
    mockStart.mockResolvedValue({ job_id: 'job-1', message: 'started' });
    mockStatus.mockResolvedValue(makeJob({ id: 'job-1', total_files: 25 }));

    const { result } = renderHook(() => useIngestion());
    await act(async () => {
      await result.current.startIngestion();
    });

    expect(result.current.job?.id).toBe('job-1');
    expect(result.current.job?.total_files).toBe(25);
  });

  it('connects WebSocket after start', async () => {
    mockStart.mockResolvedValue({ job_id: 'job-42', message: 'started' });
    mockStatus.mockResolvedValue(makeJob({ id: 'job-42' }));

    const { result } = renderHook(() => useIngestion());
    await act(async () => {
      await result.current.startIngestion();
    });

    expect(MockWebSocketManager.lastInstance?.connect).toHaveBeenCalled();
  });

  it('starting is true during the call, false after', async () => {
    let resolveStart!: (v: { job_id: string; message: string }) => void;
    mockStart.mockReturnValue(new Promise((res) => { resolveStart = res; }));
    mockStatus.mockResolvedValue(makeJob());

    const { result } = renderHook(() => useIngestion());

    act(() => { void result.current.startIngestion(); });
    expect(result.current.starting).toBe(true);

    await act(() => { resolveStart({ job_id: 'job-1', message: '' }); return Promise.resolve(); });
    await waitFor(() => expect(result.current.starting).toBe(false));
  });

  it('isRunning is true when job.status is running', async () => {
    mockStart.mockResolvedValue({ job_id: 'job-1', message: '' });
    mockStatus.mockResolvedValue(makeJob({ status: 'running' }));

    const { result } = renderHook(() => useIngestion());
    await act(async () => { await result.current.startIngestion(); });

    expect(result.current.isRunning).toBe(true);
  });
});

describe('useIngestion — startIngestion errors', () => {
  it('sets startError on API failure', async () => {
    mockStart.mockRejectedValue({ message: 'Network Error' });

    const { result } = renderHook(() => useIngestion());
    await act(async () => { await result.current.startIngestion(); });

    expect(result.current.startError).toBe('Network Error');
    expect(result.current.starting).toBe(false);
  });

  it('sets startError with 409 conflict message', async () => {
    mockStart.mockRejectedValue({ message: 'An ingestion job is already in progress.' });

    const { result } = renderHook(() => useIngestion());
    await act(async () => { await result.current.startIngestion(); });

    expect(result.current.startError).toBe('An ingestion job is already in progress.');
  });

  it('does not connect WebSocket on error', async () => {
    mockStart.mockRejectedValue({ message: 'fail' });

    const { result } = renderHook(() => useIngestion());
    await act(async () => { await result.current.startIngestion(); });

    expect(MockWebSocketManager.lastInstance).toBeNull();
  });
});

describe('useIngestion — WebSocket messages', () => {
  async function setup() {
    mockStart.mockResolvedValue({ job_id: 'job-1', message: '' });
    mockStatus.mockResolvedValue(makeJob());

    const utils = renderHook(() => useIngestion());
    await act(async () => { await utils.result.current.startIngestion(); });

    const ws = MockWebSocketManager.lastInstance!;
    return { ...utils, ws };
  }

  it('progress message updates job and currentFile', async () => {
    const { result, ws } = await setup();

    act(() => {
      ws.emit('progress', {
        type: 'progress',
        job_id: 'job-1',
        processed_files: 5,
        total_files: 10,
        progress_pct: 50,
        current_file: 'guide.pdf',
      });
    });

    expect(result.current.job?.processed_files).toBe(5);
    expect(result.current.job?.progress_pct).toBe(50);
    expect(result.current.currentFile).toBe('guide.pdf');
  });

  it('file_error message accumulates in fileErrors', async () => {
    const { result, ws } = await setup();

    act(() => {
      ws.emit('file_error', { type: 'file_error', job_id: 'job-1', file_name: 'bad.pdf', error: 'Corrupt file' });
      ws.emit('file_error', { type: 'file_error', job_id: 'job-1', file_name: 'locked.docx', error: 'Read error' });
    });

    expect(result.current.fileErrors).toHaveLength(2);
    expect(result.current.fileErrors[0].file_name).toBe('bad.pdf');
    expect(result.current.fileErrors[1].error).toBe('Read error');
  });

  it('completed message marks job as completed', async () => {
    const { result, ws } = await setup();

    act(() => {
      ws.emit('completed', {
        type: 'completed',
        job_id: 'job-1',
        total_files: 10,
        new_files: 8,
        modified_files: 2,
        deleted_files: 0,
        skipped_files: 0,
        duration_ms: 5000,
      });
    });

    expect(result.current.job?.status).toBe('completed');
    expect(result.current.job?.progress_pct).toBe(100);
    expect(result.current.currentFile).toBeNull();
    expect(result.current.isRunning).toBe(false);
    expect(ws.disconnect).toHaveBeenCalled();
  });

  it('error WS message marks job as failed', async () => {
    const { result, ws } = await setup();

    act(() => {
      ws.emit('error', { type: 'error', message: 'Pipeline crashed' });
    });

    expect(result.current.job?.status).toBe('failed');
    expect(result.current.job?.error_message).toBe('Pipeline crashed');
  });
});

describe('useIngestion — reset', () => {
  it('reset clears job, fileErrors, startError, currentFile', async () => {
    mockStart.mockResolvedValue({ job_id: 'job-1', message: '' });
    mockStatus.mockResolvedValue(makeJob());

    const { result } = renderHook(() => useIngestion());
    await act(async () => { await result.current.startIngestion(); });

    act(() => { result.current.reset(); });

    expect(result.current.job).toBeNull();
    expect(result.current.fileErrors).toEqual([]);
    expect(result.current.currentFile).toBeNull();
    expect(result.current.startError).toBeNull();
    expect(result.current.isRunning).toBe(false);
  });

  it('reset calls ws.disconnect', async () => {
    mockStart.mockResolvedValue({ job_id: 'job-1', message: '' });
    mockStatus.mockResolvedValue(makeJob());

    const { result } = renderHook(() => useIngestion());
    await act(async () => { await result.current.startIngestion(); });

    const ws = MockWebSocketManager.lastInstance!;
    act(() => { result.current.reset(); });

    expect(ws.disconnect).toHaveBeenCalled();
  });
});
