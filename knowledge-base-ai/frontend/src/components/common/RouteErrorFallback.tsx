/**
 * RouteErrorFallback — per-route error boundary fallback component.
 *
 * Catches unhandled exceptions thrown by route-level components; renders a
 * user-friendly fallback with:
 *  - Human-readable error message
 *  - Unique error ID (UUID) for support traceability
 *  - "Try Again" button that resets the boundary
 *  - "Report Issue" button that copies error details to clipboard
 *
 * Logs caught errors to the console with request_id context
 * per frontend-contract.md §6 and Constitution Principle I.
 */
import { useCallback, useEffect, useRef } from 'react';
import type { FallbackProps } from 'react-error-boundary';
import { v4 as uuidv4 } from 'uuid';

export default function RouteErrorFallback({ error, resetErrorBoundary }: FallbackProps) {
  const errorId = useRef<string>(uuidv4()).current;
  const message = error instanceof Error ? error.message : String(error);

  // Log with request_id context (Constitution §IV Structured Observability)
  useEffect(() => {
    console.error('[RouteErrorBoundary]', {
      request_id: errorId,
      error,
      message,
      timestamp: new Date().toISOString(),
      url: window.location.href,
    });
  }, [errorId, error, message]);

  const handleReportIssue = useCallback(() => {
    const details = [
      `Error: ${message}`,
      `Error ID: ${errorId}`,
      `Timestamp: ${new Date().toISOString()}`,
      `URL: ${window.location.href}`,
    ].join('\n');

    void navigator.clipboard.writeText(details).catch(() => {
      // Clipboard API may be unavailable in insecure contexts — silently ignore
    });
  }, [errorId, message]);

  return (
    <div
      role="alert"
      aria-live="assertive"
      className="route-error-boundary"
      data-testid="route-error-boundary"
    >
      <h2 className="route-error-boundary__heading">Something went wrong</h2>
      <p className="error-message" data-testid="error-message">
        {message}
      </p>
      <p className="error-id" data-testid="error-id">
        Error ID: <code>{errorId}</code>
      </p>
      <div className="error-actions">
        <button
          type="button"
          className="btn btn--primary"
          onClick={resetErrorBoundary}
          data-testid="try-again-btn"
        >
          Try again
        </button>
        <button
          type="button"
          className="btn btn--secondary"
          onClick={handleReportIssue}
          data-testid="report-issue-btn"
        >
          Report Issue
        </button>
      </div>
    </div>
  );
}
