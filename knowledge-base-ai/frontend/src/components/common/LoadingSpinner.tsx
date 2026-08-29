/**
 * Loading spinner — displayed during lazy page loading and async operations.
 *
 * Props
 * -----
 * size   — 'sm' | 'md' | 'lg' (default: 'md')
 * label  — Accessible label for screen readers (default: 'Loading…')
 */

interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg';
  label?: string;
}

const SIZE_CLASS = {
  sm: 'spinner--sm',
  md: 'spinner--md',
  lg: 'spinner--lg',
} as const;

export default function LoadingSpinner({
  size = 'md',
  label = 'Loading…',
}: LoadingSpinnerProps) {
  return (
    <div
      className={`spinner ${SIZE_CLASS[size]}`}
      role="status"
      aria-label={label}
      aria-live="polite"
    >
      <span className="spinner__circle" aria-hidden="true" />
      <span className="sr-only">{label}</span>
    </div>
  );
}
