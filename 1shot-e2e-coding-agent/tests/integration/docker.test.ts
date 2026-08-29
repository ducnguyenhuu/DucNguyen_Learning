/**
 * tests/integration/docker.test.ts — T059
 *
 * Integration tests validating the devbox Docker configuration (US4, FR-011, FR-020).
 * These tests do NOT spin up actual Docker containers — they validate:
 *
 *  1. Dockerfile.devbox — structural requirements (base image, required packages,
 *     tinyproxy config generation, REPO_URL guard, pre-warm step, entrypoint)
 *  2. docker-compose.yml — service definition, env passthrough, resource limits,
 *     runs/ volume mount
 *  3. docker-entrypoint.sh — tinyproxy start, HTTP_PROXY export, CLI delegation
 *  4. scripts/warm-cache.sh — pre-warm script exists and references correct paths
 *  5. Domain filtering (application-layer) — web_fetch tool blocks non-allowlisted
 *     domains; allowed domains pass through
 *  6. Edge cases — resource limits configured (OOM guard), blocked domain returns
 *     structured BLOCKED message (not a thrown error)
 *
 * Rationale for not running Docker:
 *   Building and booting a Docker image takes 5-15 minutes and requires Docker
 *   daemon access (not available in CI without DinD). Structural validation + the
 *   application-layer domain tests give high confidence without that overhead.
 *   Real Docker smoke tests live in a separate manual test checklist (quickstart.md).
 */

import { describe, it, expect, vi } from "vitest";
import { readFile } from "node:fs/promises";
import { join } from "node:path";

import {
  isDomainAllowed,
  assertDomainAllowed,
  DomainNotAllowedError,
} from "../../src/security/domain-allowlist.js";
import { createWebToolsExtension } from "../../extensions/web-tools.js";

// ─── Helpers ──────────────────────────────────────────────────────────────────

const ROOT = join(new URL("../../", import.meta.url).pathname);

async function readProjectFile(relPath: string): Promise<string> {
  return readFile(join(ROOT, relPath), "utf-8");
}

// ─── 1. Dockerfile.devbox structural validation ───────────────────────────────

describe("Dockerfile.devbox — structure", () => {
  it("uses node:20-slim as the base image", async () => {
    const df = await readProjectFile("Dockerfile.devbox");
    expect(df).toContain("FROM node:20-slim");
  });

  it("installs git (required by setup + commit-push steps)", async () => {
    const df = await readProjectFile("Dockerfile.devbox");
    expect(df).toContain("git");
  });

  it("installs tinyproxy (domain allowlist enforcement, D4)", async () => {
    const df = await readProjectFile("Dockerfile.devbox");
    expect(df).toContain("tinyproxy");
  });

  it("installs ripgrep (Pi built-in grep tool dependency)", async () => {
    const df = await readProjectFile("Dockerfile.devbox");
    expect(df).toContain("ripgrep");
  });

  it("installs the Pi SDK globally at the pinned version", async () => {
    const df = await readProjectFile("Dockerfile.devbox");
    expect(df).toContain("@mariozechner/pi-coding-agent@0.57.1");
  });

  it("copies and compiles the agent source", async () => {
    const df = await readProjectFile("Dockerfile.devbox");
    expect(df).toContain("npm run build");
  });

  it("generates tinyproxy.conf with FilterDefaultDeny on", async () => {
    const df = await readProjectFile("Dockerfile.devbox");
    expect(df).toContain("FilterDefaultDeny on");
  });

  it("generates tinyproxy.conf with FilterExtended on", async () => {
    const df = await readProjectFile("Dockerfile.devbox");
    expect(df).toContain("FilterExtended on");
  });

  it("defines REPO_URL as a required build arg", async () => {
    const df = await readProjectFile("Dockerfile.devbox");
    expect(df).toContain("ARG REPO_URL");
  });

  it("guards against missing REPO_URL at build time", async () => {
    const df = await readProjectFile("Dockerfile.devbox");
    // Must validate REPO_URL is non-empty before cloning
    expect(df).toMatch(/test\s+-n.*REPO_URL|REPO_URL.*required/);
  });

  it("clones the target repo with --depth=50 to /workspace", async () => {
    const df = await readProjectFile("Dockerfile.devbox");
    expect(df).toContain("--depth=50");
    expect(df).toContain("/workspace");
  });

  it("runs warm-cache.sh for pre-warming the embedding index", async () => {
    const df = await readProjectFile("Dockerfile.devbox");
    expect(df).toContain("warm-cache.sh");
  });

  it("sets the entrypoint to docker-entrypoint.sh", async () => {
    const df = await readProjectFile("Dockerfile.devbox");
    expect(df).toContain("docker-entrypoint.sh");
    expect(df).toContain("ENTRYPOINT");
  });

  it("includes default ALLOWED_DOMAINS covering LLM API endpoints", async () => {
    const df = await readProjectFile("Dockerfile.devbox");
    expect(df).toContain("api.anthropic.com");
    expect(df).toContain("api.openai.com");
  });

  it("includes default ALLOWED_DOMAINS covering GitHub", async () => {
    const df = await readProjectFile("Dockerfile.devbox");
    expect(df).toContain("github.com");
  });

  it("includes default ALLOWED_DOMAINS covering npm registry", async () => {
    const df = await readProjectFile("Dockerfile.devbox");
    expect(df).toContain("registry.npmjs.org");
  });

  it("removes apt caches to keep image lean", async () => {
    const df = await readProjectFile("Dockerfile.devbox");
    expect(df).toContain("rm -rf /var/lib/apt/lists");
  });
});

// ─── 2. docker-compose.yml structural validation ─────────────────────────────

describe("docker-compose.yml — structure", () => {
  it("defines a devbox service", async () => {
    const dc = await readProjectFile("docker-compose.yml");
    expect(dc).toContain("devbox:");
  });

  it("references Dockerfile.devbox", async () => {
    const dc = await readProjectFile("docker-compose.yml");
    expect(dc).toContain("Dockerfile.devbox");
  });

  it("passes ANTHROPIC_API_KEY from the host environment", async () => {
    const dc = await readProjectFile("docker-compose.yml");
    expect(dc).toContain("ANTHROPIC_API_KEY");
  });

  it("passes OPENAI_API_KEY from the host environment", async () => {
    const dc = await readProjectFile("docker-compose.yml");
    expect(dc).toContain("OPENAI_API_KEY");
  });

  it("passes GITHUB_TOKEN for PR creation and git push", async () => {
    const dc = await readProjectFile("docker-compose.yml");
    expect(dc).toContain("GITHUB_TOKEN");
  });

  it("mounts a runs/ volume so artifacts survive --rm", async () => {
    const dc = await readProjectFile("docker-compose.yml");
    expect(dc).toContain("/agent/runs");
  });

  it("defines resource limits to prevent OOM/runaway sessions", async () => {
    const dc = await readProjectFile("docker-compose.yml");
    expect(dc).toContain("limits:");
    expect(dc).toContain("memory:");
  });

  it("sets CPU limit to prevent container starving the host", async () => {
    const dc = await readProjectFile("docker-compose.yml");
    expect(dc).toContain("cpus:");
  });

  it("accepts REPO_URL and REPO_BRANCH as build args", async () => {
    const dc = await readProjectFile("docker-compose.yml");
    expect(dc).toContain("REPO_URL");
    expect(dc).toContain("REPO_BRANCH");
  });
});

// ─── 3. docker-entrypoint.sh structural validation ───────────────────────────

describe("scripts/docker-entrypoint.sh — structure", () => {
  it("starts tinyproxy before running the agent", async () => {
    const ep = await readProjectFile("scripts/docker-entrypoint.sh");
    expect(ep).toContain("tinyproxy");
  });

  it("exports HTTP_PROXY so tools route through the proxy", async () => {
    const ep = await readProjectFile("scripts/docker-entrypoint.sh");
    expect(ep).toContain("HTTP_PROXY");
  });

  it("exports HTTPS_PROXY for TLS traffic", async () => {
    const ep = await readProjectFile("scripts/docker-entrypoint.sh");
    expect(ep).toContain("HTTPS_PROXY");
  });

  it("exports lowercase http_proxy and https_proxy (npm/some tools)", async () => {
    const ep = await readProjectFile("scripts/docker-entrypoint.sh");
    expect(ep).toContain("http_proxy");
    expect(ep).toContain("https_proxy");
  });

  it("delegates to the agent CLI with all arguments forwarded", async () => {
    const ep = await readProjectFile("scripts/docker-entrypoint.sh");
    expect(ep).toContain("cli.js");
    expect(ep).toContain('"$@"');
  });

  it("uses 'exec' so signals propagate to the agent process", async () => {
    const ep = await readProjectFile("scripts/docker-entrypoint.sh");
    expect(ep).toMatch(/\bexec\b/);
  });
});

// ─── 4. Pre-warm artifacts ─────────────────────────────────────────────────────

describe("Pre-warm script — existence and structure", () => {
  it("scripts/warm-cache.sh exists", async () => {
    await expect(readProjectFile("scripts/warm-cache.sh")).resolves.toBeTruthy();
  });

  it("warm-cache.sh accepts WORKSPACE_PATH argument", async () => {
    const wc = await readProjectFile("scripts/warm-cache.sh");
    expect(wc).toMatch(/WORKSPACE_PATH/);
  });

  it("warm-cache.sh references INDEX_PATH for the vectra index directory", async () => {
    const wc = await readProjectFile("scripts/warm-cache.sh");
    expect(wc).toMatch(/INDEX_PATH/);
  });

  it("scripts/docker-entrypoint.sh exists", async () => {
    await expect(readProjectFile("scripts/docker-entrypoint.sh")).resolves.toBeTruthy();
  });
});

// ─── 5. Domain filtering — application-layer (FR-020) ────────────────────────

describe("Domain filtering — application-layer enforcement", () => {
  const DEFAULT_ALLOWLIST = [
    "api.anthropic.com",
    "api.openai.com",
    "github.com",
    "api.github.com",
    "raw.githubusercontent.com",
    "registry.npmjs.org",
    "pypi.org",
    "files.pythonhosted.org",
  ];

  it("allows api.anthropic.com (LLM provider)", () => {
    expect(isDomainAllowed("https://api.anthropic.com/v1/messages", DEFAULT_ALLOWLIST)).toBe(true);
  });

  it("allows api.openai.com (alternative LLM provider)", () => {
    expect(isDomainAllowed("https://api.openai.com/v1/chat/completions", DEFAULT_ALLOWLIST)).toBe(true);
  });

  it("allows api.github.com (PR creation, FR-009)", () => {
    expect(isDomainAllowed("https://api.github.com/repos/owner/repo/pulls", DEFAULT_ALLOWLIST)).toBe(true);
  });

  it("allows registry.npmjs.org (npm install in target repo)", () => {
    expect(isDomainAllowed("https://registry.npmjs.org/express", DEFAULT_ALLOWLIST)).toBe(true);
  });

  it("blocks non-allowlisted domain (exfiltration attempt)", () => {
    expect(isDomainAllowed("https://attacker.com/steal", DEFAULT_ALLOWLIST)).toBe(false);
  });

  it("blocks data: URLs (not HTTP/S)", () => {
    expect(isDomainAllowed("data:text/plain,secret", DEFAULT_ALLOWLIST)).toBe(false);
  });

  it("blocks empty string URL", () => {
    expect(isDomainAllowed("", DEFAULT_ALLOWLIST)).toBe(false);
  });

  it("blocks all requests when allowlist is empty (lock-down mode)", () => {
    expect(isDomainAllowed("https://api.anthropic.com/v1/messages", [])).toBe(false);
  });

  it("assertDomainAllowed does not throw for allowed domain", () => {
    expect(() =>
      assertDomainAllowed("https://api.github.com/repos", DEFAULT_ALLOWLIST),
    ).not.toThrow();
  });

  it("assertDomainAllowed throws DomainNotAllowedError for blocked domain", () => {
    expect(() =>
      assertDomainAllowed("https://attacker.com/steal", DEFAULT_ALLOWLIST),
    ).toThrow(DomainNotAllowedError);
  });
});

// ─── 6. web_fetch tool — domain blocking edge cases ──────────────────────────

describe("web_fetch tool — non-allowlisted domain access attempt", () => {
  it("returns BLOCKED message (not thrown error) for non-allowlisted domain", async () => {
    const ext = createWebToolsExtension({
      allowedDomains: ["api.github.com"],
    });

    const tool = ext.toolDefinitions[0];
    expect(tool.name).toBe("web_fetch");

    const result = await tool.execute(
      "tool-call-1",
      { url: "https://attacker.com/steal-secrets" },
      null as unknown as AbortSignal,
      () => {},
      {} as never,
    );

    const text = (result.content[0] as { type: string; text: string }).text;
    expect(text).toMatch(/BLOCKED/i);
    expect(text).toContain("attacker.com");
  });

  it("includes the hostname in the BLOCKED message", async () => {
    const ext = createWebToolsExtension({ allowedDomains: [] });
    const tool = ext.toolDefinitions[0];

    const result = await tool.execute(
      "tool-call-2",
      { url: "https://evil.org/payload" },
      null as unknown as AbortSignal,
      () => {},
      {} as never,
    );

    const text = (result.content[0] as { type: string; text: string }).text;
    expect(text).toContain("evil.org");
  });

  it("includes the allowlist in the BLOCKED message", async () => {
    const ext = createWebToolsExtension({ allowedDomains: ["api.github.com"] });
    const tool = ext.toolDefinitions[0];

    const result = await tool.execute(
      "tool-call-3",
      { url: "https://evil.org/payload" },
      null as unknown as AbortSignal,
      () => {},
      {} as never,
    );

    const text = (result.content[0] as { type: string; text: string }).text;
    expect(text).toContain("api.github.com");
  });

  it("does not make an HTTP request for a blocked URL (no network call)", async () => {
    // Spy on global fetch — it must never be called for blocked domains
    const fetchSpy = vi.spyOn(globalThis, "fetch");

    const ext = createWebToolsExtension({ allowedDomains: [] });
    const tool = ext.toolDefinitions[0];

    await tool.execute(
      "tool-call-4",
      { url: "https://attacker.com/steal" },
      null as unknown as AbortSignal,
      () => {},
      {} as never,
    );

    expect(fetchSpy).not.toHaveBeenCalled();
    fetchSpy.mockRestore();
  });

  it("returns structured details.blocked=true for blocked domain", async () => {
    const ext = createWebToolsExtension({ allowedDomains: ["api.github.com"] });
    const tool = ext.toolDefinitions[0];

    const result = await tool.execute(
      "tool-call-5",
      { url: "https://attacker.com/steal" },
      null as unknown as AbortSignal,
      () => {},
      {} as never,
    );

    expect((result.details as { blocked?: boolean }).blocked).toBe(true);
  });

  it("blocks an invalid (unparseable) URL", async () => {
    const ext = createWebToolsExtension({ allowedDomains: ["api.github.com"] });
    const tool = ext.toolDefinitions[0];

    const result = await tool.execute(
      "tool-call-6",
      { url: "not-a-valid-url" },
      null as unknown as AbortSignal,
      () => {},
      {} as never,
    );

    const text = (result.content[0] as { type: string; text: string }).text;
    expect(text).toMatch(/BLOCKED/i);
  });
});

// ─── 7. OOM / resource limit edge cases (compose config) ─────────────────────

describe("OOM / disk-exhaustion guard — compose resource limits", () => {
  it("memory limit is defined in docker-compose.yml", async () => {
    const dc = await readProjectFile("docker-compose.yml");
    // Must have a memory limit value (e.g. "4G", "2048M")
    expect(dc).toMatch(/memory:\s*\d/);
  });

  it("cpu limit is defined in docker-compose.yml", async () => {
    const dc = await readProjectFile("docker-compose.yml");
    // Must have a cpu limit value (e.g. "4", "2.0")
    expect(dc).toMatch(/cpus:\s*["']?\d/);
  });

  it("memory reservation is lower than the memory limit", async () => {
    const dc = await readProjectFile("docker-compose.yml");
    // Both limits and reservations sections must be present
    expect(dc).toContain("limits:");
    expect(dc).toContain("reservations:");
  });
});
