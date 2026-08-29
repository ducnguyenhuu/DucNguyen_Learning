/**
 * Unit tests for RouteErrorFallback component.
 *
 * Covers:
 * - Shows "Something went wrong" heading
 * - Displays the error message
 * - Displays a unique error ID
 * - Has role="alert" for accessibility
 * - "Try again" button resets the boundary
 * - "Report Issue" button is present
 * - "Report Issue" copies details to clipboard
 * - Logs error to console with request_id context
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ErrorBoundary } from 'react-error-boundary';
import RouteErrorFallback from './RouteErrorFallback';

// ── Helpers ────────────────────────────────────────────────────────────────

/** A component that throws synchronously — used to trigger boundaries in tests. */
function Thrower({ message = 'test error' }: { message?: string }): never {
  throw new Error(message);
}

function renderWithBoundary(throwMessage = 'test error') {
  return render(
    <ErrorBoundary FallbackComponent={RouteErrorFallback}>
      <Thrower message={throwMessage} />
    </ErrorBoundary>,
  );
}

// ── Tests ──────────────────────────────────────────────────────────────────

describe('RouteErrorFallback', () => {
  const mockWriteText = vi.fn();

  beforeEach(() => {
    // Re-apply implementation each beforeEach so vi.resetAllMocks() in afterEach
    // doesn't leave writeText returning undefined.
    mockWriteText.mockResolvedValue(undefined);

    // jsdom never defines navigator.clipboard — set it up here
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText: mockWriteText },
      writable: true,
      configurable: true,
    });

    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    // restoreAllMocks restores console.error spy; also resets vi.fn() impls,
    // which is fine because beforeEach re-registers them.
    vi.restoreAllMocks();
  });

  // ── Rendering ────────────────────────────────────────────────────────────
  it('shows "Something went wrong" heading', () => {
    renderWithBoundary();
    expect(screen.getByRole('heading', { name: /something went wrong/i })).toBeInTheDocument();
  });

  it('displays the thrown error message', () => {
    renderWithBoundary('disk full');
    expect(screen.getByTestId('error-message')).toHaveTextContent('disk full');
  });

  it('displays a unique error ID', () => {
    renderWithBoundary();
    const errorId = screen.getByTestId('error-id');
    expect(errorId).toBeInTheDocument();
    // UUID v4 pattern
    expect(errorId.textContent).toMatch(
      /[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}/i,
    );
  });

  it('has role="alert" for accessibility', () => {
    renderWithBoundary();
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });

  // ── Buttons ──────────────────────────────────────────────────────────────
  it('shows "Try again" button', () => {
    renderWithBoundary();
    expect(screen.getByTestId('try-again-btn')).toBeInTheDocument();
  });

  it('shows "Report Issue" button', () => {
    renderWithBoundary();
    expect(screen.getByTestId('report-issue-btn')).toBeInTheDocument();
  });

  it('"Try again" resets the boundary and shows recovered content', async () => {
    let shouldThrow = true;

    function MaybeThrow() {
      if (shouldThrow) throw new Error('transient error');
      return <div data-testid="recovered">Recovered</div>;
    }

    render(
      <ErrorBoundary FallbackComponent={RouteErrorFallback}>
        <MaybeThrow />
      </ErrorBoundary>,
    );

    expect(screen.getByRole('alert')).toBeInTheDocument();

    // Fix the component before resetting
    shouldThrow = false;
    await userEvent.click(screen.getByTestId('try-again-btn'));

    expect(screen.getByTestId('recovered')).toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('"Report Issue" copies details to clipboard', async () => {
    renderWithBoundary('clipboard error test');
    await userEvent.click(screen.getByTestId('report-issue-btn'));

    await waitFor(() => {
      expect(mockWriteText).toHaveBeenCalledOnce();
    });

    const clipboardText = (mockWriteText.mock.calls[0] as unknown[])[0] as string;
    expect(clipboardText).toContain('clipboard error test');
    expect(clipboardText).toMatch(/Error ID:/);
  });

  it('"Report Issue" clipboard text includes URL', async () => {
    renderWithBoundary();
    await userEvent.click(screen.getByTestId('report-issue-btn'));

    await waitFor(() => expect(mockWriteText).toHaveBeenCalledOnce());

    const clipboardText = (mockWriteText.mock.calls[0] as unknown[])[0] as string;
    expect(clipboardText).toMatch(/URL:/);
  });

  // ── Logging ──────────────────────────────────────────────────────────────
  it('logs error to console with request_id on mount', () => {
    renderWithBoundary('logged error');

    expect(console.error).toHaveBeenCalledWith(
      '[RouteErrorBoundary]',
      expect.objectContaining({
        request_id: expect.any(String) as unknown,
        message: 'logged error',
      }),
    );
  });

  it('logged request_id matches displayed error ID', () => {
    renderWithBoundary();

    const calls = vi.mocked(console.error).mock.calls;
    const boundaryCall = calls.find(
      (args) => typeof args[0] === 'string' && args[0] === '[RouteErrorBoundary]',
    );
    expect(boundaryCall).toBeDefined();
    const logged = (boundaryCall as unknown[])[1] as { request_id: string };

    const errorId = screen.getByTestId('error-id').textContent ?? '';
    expect(errorId).toContain(logged.request_id);
  });
});
