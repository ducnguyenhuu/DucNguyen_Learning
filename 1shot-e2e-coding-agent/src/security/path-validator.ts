/**
 * src/security/path-validator.ts — Path validation (FR-019)
 *
 * Restricts all file I/O to the cloned repository directory.
 * Any path that resolves outside the repo root is blocked.
 *
 * Why this matters (FR-019):
 *   A prompt-injected command could try to read /etc/passwd or write to ~/.ssh/.
 *   Real-path resolution + prefix check ensures that even clever traversal
 *   sequences (../../) and symlinks pointing outside the repo are caught.
 *
 * Exports:
 *  - PathValidationError  — thrown by assertPathAllowed()
 *  - isPathAllowed()      — returns boolean, safe to call in hot paths
 *  - assertPathAllowed()  — throws PathValidationError on violation, returns resolved path
 */

import { realpathSync, existsSync } from "node:fs";
import { resolve, normalize } from "node:path";

// ─── PathValidationError ──────────────────────────────────────────────────────

export class PathValidationError extends Error {
  override readonly name = "PathValidationError";
  readonly attemptedPath: string;
  readonly repoRoot: string;

  constructor(attemptedPath: string, repoRoot: string) {
    super(
      `Path validation failed: "${attemptedPath}" is outside the allowed repo root "${repoRoot}"`,
    );
    this.attemptedPath = attemptedPath;
    this.repoRoot = repoRoot;
  }
}

// ─── Internal helpers ─────────────────────────────────────────────────────────

/**
 * Normalize and resolve a path without requiring it to exist on disk.
 * Uses Node's path.resolve() for lexical normalization (handles ../).
 */
function lexicalResolve(p: string): string {
  return normalize(resolve(p));
}

/**
 * Attempt to resolve the real (symlink-dereferenced) path.
 * Falls back to lexical resolution if the path does not exist yet
 * (e.g. a new file being written for the first time).
 */
function safRealpath(p: string): string {
  if (!p) return "";
  try {
    if (existsSync(p)) {
      return realpathSync(p);
    }
  } catch {
    // Path may not exist yet — fall through to lexical resolution
  }
  return lexicalResolve(p);
}

/**
 * Ensure the normalised root ends with a path separator so that
 * "/workspace/repo-extra" is NOT treated as being inside "/workspace/repo".
 * Also resolves symlinks in the root itself (e.g. /tmp → /private/tmp on macOS).
 */
function normaliseRoot(root: string): string {
  if (!root) return "";
  const r = safRealpath(root);
  if (!r) return "";
  return r.endsWith("/") ? r : r + "/";
}

// ─── isPathAllowed ────────────────────────────────────────────────────────────

/**
 * Return true if `targetPath` resolves inside `repoRoot`.
 *
 * Handles:
 *  - Directory traversal sequences (../../)
 *  - Absolute paths outside the repo
 *  - Symlinks whose real target is outside the repo
 *  - Empty strings
 */
export function isPathAllowed(targetPath: string, repoRoot: string): boolean {
  if (!targetPath || !repoRoot) return false;

  const resolvedTarget = safRealpath(targetPath);
  const normalisedRoot = normaliseRoot(repoRoot);

  // A path is valid if it equals the root exactly, or starts with root + "/"
  return (
    resolvedTarget === normalisedRoot.slice(0, -1) || // root itself (strip trailing /)
    resolvedTarget.startsWith(normalisedRoot)
  );
}

// ─── assertPathAllowed ────────────────────────────────────────────────────────

/**
 * Assert that `targetPath` resolves inside `repoRoot`.
 *
 * @returns The resolved absolute path (suitable for use in file operations)
 * @throws  PathValidationError when the path is outside the repo root
 */
export function assertPathAllowed(targetPath: string, repoRoot: string): string {
  if (!isPathAllowed(targetPath, repoRoot)) {
    throw new PathValidationError(targetPath, repoRoot);
  }
  return safRealpath(targetPath);
}
