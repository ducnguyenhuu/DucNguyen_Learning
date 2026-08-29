/**
 * ReembedBanner — persistent info banner displayed on all pages while
 * the backend is re-embedding documents due to a model change (FR-021).
 *
 * Behaviour (per frontend-contract.md §8.16):
 * - Shown on all pages when GET /health returns `reembedding: true`.
 * - Dismissed automatically when `reembedding` returns to `false`.
 * - Provides a "View Progress" link to /documents.
 *
 * Accessibility:
 * - role="alert" / aria-live="polite" so screen readers announce the banner.
 */
import { Link } from 'react-router-dom';
import { useHealth } from '../../hooks/useHealth';

export default function ReembedBanner() {
  const { health } = useHealth();

  if (!health?.reembedding) {
    return null;
  }

  return (
    <div
      role="alert"
      aria-live="polite"
      className="reembed-banner"
      data-testid="reembed-banner"
    >
      <span className="reembed-banner__icon" aria-hidden="true">ℹ️</span>
      <span className="reembed-banner__text">
        Re-embedding documents due to model update…
      </span>
      <Link
        to="/documents"
        className="reembed-banner__link"
      >
        View Progress
      </Link>
    </div>
  );
}
