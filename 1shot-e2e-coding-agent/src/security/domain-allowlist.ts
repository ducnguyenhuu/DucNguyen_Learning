/**
 * src/security/domain-allowlist.ts — Domain allowlist enforcement (FR-020)
 *
 * Restricts outbound HTTP/S requests to a configured list of allowed domains.
 * Used by the web-tools Pi Extension (T058) and any other module that fetches
 * external URLs, ensuring the agent cannot exfiltrate data to arbitrary hosts.
 *
 * Why this matters (FR-020):
 *   A prompt-injected instruction could try to POST secrets to attacker.com.
 *   An explicit allowlist (backed by tinyproxy in production) ensures only
 *   pre-approved domains are reachable during a run.
 *
 * Wildcard support:
 *   "*.github.com" matches "api.github.com" and "raw.github.com" but NOT
 *   "github.com" itself (bare domain). This follows tinyproxy's Allow syntax.
 *
 * Exports:
 *  - DomainNotAllowedError  — thrown by assertDomainAllowed()
 *  - isDomainAllowed()      — returns boolean, safe for hot-path checks
 *  - assertDomainAllowed()  — throws DomainNotAllowedError on violation
 *  - loadDomainAllowlist()  — extracts the allowlist from an AgentConfig
 */

import type { AgentConfig } from "../types.js";

// ─── DomainNotAllowedError ────────────────────────────────────────────────────

export class DomainNotAllowedError extends Error {
  override readonly name = "DomainNotAllowedError";
  /** The full URL that was blocked. */
  readonly url: string;
  /** The allowlist that was active when the URL was blocked. */
  readonly allowedDomains: string[];

  constructor(url: string, allowedDomains: string[]) {
    // Extract hostname for the message — fall back to the raw url if parsing fails
    let hostname: string;
    try {
      hostname = new URL(url).hostname;
    } catch {
      hostname = url;
    }
    super(
      `Domain not allowed: "${hostname}" is not in the configured domain allowlist. ` +
        `Allowed domains: [${allowedDomains.join(", ") || "(none)"}]`,
    );
    this.url = url;
    this.allowedDomains = allowedDomains;
  }
}

// ─── Internal helpers ─────────────────────────────────────────────────────────

/**
 * Extract the lowercase hostname from a URL string.
 * Returns null if the URL cannot be parsed (invalid, plain string with no scheme, etc.).
 */
function extractHostname(url: string): string | null {
  if (!url) return null;
  try {
    return new URL(url).hostname.toLowerCase();
  } catch {
    return null;
  }
}

/**
 * Test whether `hostname` matches a single allowlist `entry`.
 *
 * Matching rules:
 *  - Exact match (case-insensitive): "api.github.com" matches "api.github.com"
 *  - Wildcard prefix: "*.github.com" matches "api.github.com" but NOT "github.com"
 */
function matchesEntry(hostname: string, entry: string): boolean {
  const normalizedEntry = entry.toLowerCase();

  if (normalizedEntry.startsWith("*.")) {
    // Wildcard: strip the "*." and check that hostname ends with ".{rest}"
    const suffix = normalizedEntry.slice(1); // e.g. ".github.com"
    return hostname.endsWith(suffix) && hostname.length > suffix.length;
  }

  return hostname === normalizedEntry;
}

// ─── Public API ───────────────────────────────────────────────────────────────

/**
 * Return true if the URL's hostname is permitted by the allowlist.
 *
 * Returns false for:
 *  - Invalid/unparseable URLs
 *  - Empty URL strings
 *  - Empty allowlist (block-all policy)
 *  - Hostnames not matched by any allowlist entry
 */
export function isDomainAllowed(url: string, allowedDomains: string[]): boolean {
  const hostname = extractHostname(url);
  if (hostname === null) return false;
  if (allowedDomains.length === 0) return false;
  return allowedDomains.some((entry) => matchesEntry(hostname, entry));
}

/**
 * Assert that the URL's hostname is permitted by the allowlist.
 * Throws DomainNotAllowedError if not allowed; returns void on success.
 */
export function assertDomainAllowed(url: string, allowedDomains: string[]): void {
  if (!isDomainAllowed(url, allowedDomains)) {
    throw new DomainNotAllowedError(url, allowedDomains);
  }
}

/**
 * Extract the domain allowlist from an AgentConfig.
 * Returns an empty array when the config does not specify a list.
 */
export function loadDomainAllowlist(config: AgentConfig): string[] {
  return config.security?.domainAllowlist ?? [];
}
