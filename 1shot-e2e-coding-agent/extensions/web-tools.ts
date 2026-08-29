/**
 * extensions/web-tools.ts — Web-tools Pi Extension (US4, T058)
 *
 * Registers one custom tool with the Pi SDK:
 *  - web_fetch : fetch a URL and return its text content
 *
 * Security boundary (FR-020, Architecture Decision D4):
 *   Every fetch is validated against a domain allowlist BEFORE the HTTP request
 *   is made. If the URL's hostname is not in the allowlist, the tool returns an
 *   error message to the agent rather than throwing — this ensures the agent
 *   receives useful feedback ("domain not allowed") instead of a crash.
 *
 *   In production the container also runs tinyproxy that enforces the same list
 *   at the network layer (defence-in-depth); this check is the application-layer
 *   guard so prompt-injected URLs are caught first.
 *
 * Usage:
 *   const ext = createWebToolsExtension({ allowedDomains: ["api.github.com"] });
 *   // Pass to Pi SDK session:
 *   const sdkOptions = { ..., customTools: ext.toolDefinitions };
 */

import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "@mariozechner/pi-coding-agent";
import { isDomainAllowed } from "../src/security/domain-allowlist.js";

// ─── Types ────────────────────────────────────────────────────────────────────

export interface WebToolsOptions {
  /**
   * Domains the agent is allowed to fetch from.
   * Supports exact matches ("api.github.com") and wildcard subdomain matches
   * ("*.github.com" matches "api.github.com" but NOT "github.com").
   * An empty array blocks all requests.
   */
  allowedDomains: string[];
  /**
   * Maximum response body size in bytes.
   * Responses exceeding this limit are truncated.
   * Default: 512_000 (512 KB)
   */
  maxBodyBytes?: number;
  /**
   * Fetch timeout in milliseconds.
   * Default: 30_000 (30 s)
   */
  timeoutMs?: number;
}

/** Shape returned by the factory function. */
export interface WebToolsExtension {
  /** Extension name identifier. */
  name: string;
  /** Names of the registered tools (for documentation / inspection). */
  tools: string[];
  /**
   * Actual Pi SDK ToolDefinition objects.
   * Pass these to `customTools` in `CreateAgentSessionOptions`.
   */
  toolDefinitions: ToolDefinition[];
}

// ─── Private helpers ──────────────────────────────────────────────────────────

/**
 * Decode a Response body as text, truncating at `maxBytes` if needed.
 * Returns the text and a boolean indicating whether truncation occurred.
 */
async function readBodyText(
  response: Response,
  maxBytes: number,
): Promise<{ text: string; truncated: boolean }> {
  const buffer = await response.arrayBuffer();
  const bytes = new Uint8Array(buffer);

  if (bytes.length <= maxBytes) {
    return { text: new TextDecoder().decode(bytes), truncated: false };
  }

  const truncatedBytes = bytes.slice(0, maxBytes);
  return { text: new TextDecoder().decode(truncatedBytes), truncated: true };
}

/**
 * Produce a structured result string for the web_fetch tool output.
 */
function formatFetchResult(
  url: string,
  status: number,
  contentType: string,
  body: string,
  truncated: boolean,
): string {
  const lines = [
    `URL: ${url}`,
    `Status: ${status}`,
    `Content-Type: ${contentType}`,
    truncated ? `(Response truncated — showing first ${body.length} bytes)` : "",
    "",
    body,
  ];
  return lines.filter((l) => l !== "").join("\n");
}

// ─── createWebToolsExtension ──────────────────────────────────────────────────

/**
 * Factory function that creates and returns a web-tools Pi Extension.
 *
 * The returned `toolDefinitions` array can be passed to `customTools` in the
 * Pi SDK `CreateAgentSessionOptions` so context-gather or other agent nodes
 * can fetch documentation or issue content from pre-approved domains.
 *
 * All tools are synchronous to construct (no I/O at factory call time).
 * I/O happens only when the agent actually invokes a tool during execution.
 */
export function createWebToolsExtension(options: WebToolsOptions): WebToolsExtension {
  const {
    allowedDomains,
    maxBodyBytes = 512_000,
    timeoutMs = 30_000,
  } = options;

  // ── Tool: web_fetch ────────────────────────────────────────────────────────

  const webFetchTool: ToolDefinition = {
    name: "web_fetch",
    label: "Fetch Web Page",
    description:
      "Fetch the content of a URL and return it as text. " +
      "Use this to read documentation pages, GitHub issues, or public API specs. " +
      `Only URLs from approved domains are allowed (${allowedDomains.length > 0 ? allowedDomains.join(", ") : "none configured"}). ` +
      "Provide the full URL including scheme (https://...). " +
      "Large responses are automatically truncated.",
    promptSnippet: "web_fetch({ url }) → page content as text",
    parameters: Type.Object({
      url: Type.String({
        description: "The full URL to fetch (https://... or http://...).",
      }),
      headers: Type.Optional(
        Type.Record(Type.String(), Type.String(), {
          description: "Optional extra HTTP request headers (e.g. { Accept: 'application/json' }).",
        }),
      ),
    }),
    async execute(_toolCallId, params, signal, _onUpdate, _ctx) {
      const { url, headers: extraHeaders = {} } = params as {
        url: string;
        headers?: Record<string, string>;
      };

      // ── Application-layer allowlist check (FR-020) ─────────────────────
      if (!isDomainAllowed(url, allowedDomains)) {
        let hostname = url;
        try {
          hostname = new URL(url).hostname;
        } catch {
          // Keep raw url in message if unparseable
        }
        const text =
          `BLOCKED: Domain "${hostname}" is not in the configured allowlist.\n` +
          `Allowed domains: ${allowedDomains.length > 0 ? allowedDomains.join(", ") : "(none)"}`;
        return {
          content: [{ type: "text" as const, text }],
          details: { blocked: true, url },
        };
      }

      // ── Perform the fetch ──────────────────────────────────────────────
      const abortController = new AbortController();
      const timeoutHandle = setTimeout(() => abortController.abort(), timeoutMs);

      // Merge the signal from the tool caller with our timeout signal
      if (signal) {
        signal.addEventListener("abort", () => abortController.abort(), { once: true });
      }

      let response: Response;
      try {
        response = await fetch(url, {
          method: "GET",
          headers: {
            "User-Agent": "1shot-coding-agent/0.1 (web_fetch tool)",
            ...extraHeaders,
          },
          signal: abortController.signal,
        });
      } catch (err) {
        clearTimeout(timeoutHandle);
        const msg = err instanceof Error ? err.message : String(err);
        const text = `ERROR: Fetch failed — ${msg}`;
        return {
          content: [{ type: "text" as const, text }],
          details: { error: msg, url },
        };
      } finally {
        clearTimeout(timeoutHandle);
      }

      // ── Read and optionally truncate the response body ─────────────────
      let body: string;
      let truncated: boolean;
      try {
        ({ text: body, truncated } = await readBodyText(response, maxBodyBytes));
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        const text = `ERROR: Failed to read response body — ${msg}`;
        return {
          content: [{ type: "text" as const, text }],
          details: { error: msg, url, status: response.status },
        };
      }

      const contentType = response.headers.get("content-type") ?? "unknown";
      const text = formatFetchResult(url, response.status, contentType, body, truncated);

      return {
        content: [{ type: "text" as const, text }],
        details: {
          url,
          status: response.status,
          contentType,
          truncated,
          bodyLength: body.length,
        },
      };
    },
  };

  return {
    name: "web-tools",
    tools: ["web_fetch"],
    toolDefinitions: [webFetchTool],
  };
}
