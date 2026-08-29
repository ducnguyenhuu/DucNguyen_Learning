/**
 * tests/unit/security/domain-allowlist.test.ts — T054
 *
 * Tests for src/security/domain-allowlist.ts
 *
 * What is tested (FR-020):
 *  - isDomainAllowed(): accepts URLs whose hostname is in the allowlist
 *  - isDomainAllowed(): rejects URLs whose hostname is NOT in the allowlist
 *  - isDomainAllowed(): empty allowlist blocks everything
 *  - isDomainAllowed(): wildcard entry "*.example.com" matches subdomains
 *  - isDomainAllowed(): wildcard does NOT match the bare domain itself
 *  - isDomainAllowed(): handles https:// and http:// scheme URLs
 *  - isDomainAllowed(): handles ports in URLs
 *  - isDomainAllowed(): case-insensitive hostname matching
 *  - assertDomainAllowed(): throws DomainNotAllowedError on violation
 *  - assertDomainAllowed(): passes silently for allowed domains
 *  - DomainNotAllowedError: exposes the blocked URL and allowlist
 *  - loadDomainAllowlist(): extracts allowlist from AgentConfig
 *  - Edge cases: invalid URL string, plain hostname (no scheme)
 */

import { describe, it, expect } from "vitest";
import type { AgentConfig } from "../../../src/types.js";
import { DEFAULT_CONFIG } from "../../../src/config.js";
import {
  isDomainAllowed,
  assertDomainAllowed,
  loadDomainAllowlist,
  DomainNotAllowedError,
} from "../../../src/security/domain-allowlist.js";

// ─── isDomainAllowed() ────────────────────────────────────────────────────────

describe("isDomainAllowed()", () => {
  it("returns true when the URL's hostname matches an exact allowlist entry", () => {
    expect(isDomainAllowed("https://api.github.com/repos", ["api.github.com"])).toBe(true);
  });

  it("returns false when the URL's hostname is not in the allowlist", () => {
    expect(isDomainAllowed("https://evil.com/steal", ["api.github.com"])).toBe(false);
  });

  it("returns false when the allowlist is empty (block all)", () => {
    expect(isDomainAllowed("https://api.github.com/repos", [])).toBe(false);
  });

  it("returns true for http:// scheme URLs", () => {
    expect(isDomainAllowed("http://registry.npmjs.org/package", ["registry.npmjs.org"])).toBe(true);
  });

  it("returns true when URL contains a port and the domain matches", () => {
    expect(isDomainAllowed("https://api.github.com:443/repos", ["api.github.com"])).toBe(true);
  });

  it("returns true for wildcard entry matching a subdomain", () => {
    expect(isDomainAllowed("https://api.github.com/repos", ["*.github.com"])).toBe(true);
  });

  it("returns true for another subdomain matching the same wildcard", () => {
    expect(isDomainAllowed("https://raw.github.com/file", ["*.github.com"])).toBe(true);
  });

  it("returns false when wildcard does NOT match the bare domain (github.com)", () => {
    expect(isDomainAllowed("https://github.com/login", ["*.github.com"])).toBe(false);
  });

  it("returns false when wildcard does not match a different domain", () => {
    expect(isDomainAllowed("https://evil.com/steal", ["*.github.com"])).toBe(false);
  });

  it("matches case-insensitively (uppercase hostname in URL)", () => {
    expect(isDomainAllowed("https://API.GITHUB.COM/repos", ["api.github.com"])).toBe(true);
  });

  it("matches case-insensitively (uppercase hostname in allowlist entry)", () => {
    expect(isDomainAllowed("https://api.github.com/repos", ["API.GITHUB.COM"])).toBe(true);
  });

  it("returns true when one of multiple allowlist entries matches", () => {
    expect(
      isDomainAllowed("https://registry.npmjs.org/package", [
        "api.github.com",
        "registry.npmjs.org",
        "pypi.org",
      ]),
    ).toBe(true);
  });

  it("returns false for a URL that partially matches but not the hostname", () => {
    // 'github.com' in path, not host
    expect(isDomainAllowed("https://evil.com/redirect?to=github.com", ["github.com"])).toBe(false);
  });

  it("returns false for an invalid URL string", () => {
    expect(isDomainAllowed("not-a-url", ["not-a-url"])).toBe(false);
  });

  it("returns false for an empty URL string", () => {
    expect(isDomainAllowed("", ["github.com"])).toBe(false);
  });
});

// ─── assertDomainAllowed() ────────────────────────────────────────────────────

describe("assertDomainAllowed()", () => {
  it("does not throw when the URL is in the allowlist", () => {
    expect(() =>
      assertDomainAllowed("https://api.github.com/repos", ["api.github.com"]),
    ).not.toThrow();
  });

  it("throws DomainNotAllowedError when the URL is not in the allowlist", () => {
    expect(() =>
      assertDomainAllowed("https://evil.com/steal", ["api.github.com"]),
    ).toThrow(DomainNotAllowedError);
  });

  it("throws DomainNotAllowedError when the allowlist is empty", () => {
    expect(() =>
      assertDomainAllowed("https://api.github.com/repos", []),
    ).toThrow(DomainNotAllowedError);
  });

  it("throws an error with a message mentioning the blocked URL", () => {
    try {
      assertDomainAllowed("https://evil.com/steal", ["api.github.com"]);
      expect.fail("should have thrown");
    } catch (err) {
      expect((err as Error).message).toContain("evil.com");
    }
  });

  it("does not throw when wildcard entry matches the URL subdomain", () => {
    expect(() =>
      assertDomainAllowed("https://raw.github.com/file", ["*.github.com"]),
    ).not.toThrow();
  });
});

// ─── DomainNotAllowedError ────────────────────────────────────────────────────

describe("DomainNotAllowedError", () => {
  it("is an instance of Error", () => {
    const err = new DomainNotAllowedError("https://evil.com", ["api.github.com"]);
    expect(err).toBeInstanceOf(Error);
  });

  it("has name DomainNotAllowedError", () => {
    const err = new DomainNotAllowedError("https://evil.com", ["api.github.com"]);
    expect(err.name).toBe("DomainNotAllowedError");
  });

  it("exposes the blocked URL on .url", () => {
    const err = new DomainNotAllowedError("https://evil.com", ["api.github.com"]);
    expect(err.url).toBe("https://evil.com");
  });

  it("exposes the allowlist on .allowedDomains", () => {
    const list = ["api.github.com", "pypi.org"];
    const err = new DomainNotAllowedError("https://evil.com", list);
    expect(err.allowedDomains).toEqual(list);
  });

  it("message includes the hostname", () => {
    const err = new DomainNotAllowedError("https://evil.com/path", ["api.github.com"]);
    expect(err.message).toContain("evil.com");
  });
});

// ─── loadDomainAllowlist() ────────────────────────────────────────────────────

describe("loadDomainAllowlist()", () => {
  it("returns the domainAllowlist array from config.security", () => {
    const config: AgentConfig = {
      ...DEFAULT_CONFIG,
      security: { domainAllowlist: ["api.github.com", "registry.npmjs.org"] },
    };
    expect(loadDomainAllowlist(config)).toEqual(["api.github.com", "registry.npmjs.org"]);
  });

  it("returns an empty array when config.security is undefined", () => {
    const config: AgentConfig = { ...DEFAULT_CONFIG, security: undefined };
    expect(loadDomainAllowlist(config)).toEqual([]);
  });

  it("returns an empty array when domainAllowlist is undefined", () => {
    const config: AgentConfig = { ...DEFAULT_CONFIG, security: {} };
    expect(loadDomainAllowlist(config)).toEqual([]);
  });

  it("returns an empty array when domainAllowlist is an empty array", () => {
    const config: AgentConfig = { ...DEFAULT_CONFIG, security: { domainAllowlist: [] } };
    expect(loadDomainAllowlist(config)).toEqual([]);
  });

  it("returns the same reference as provided in config (no copy needed)", () => {
    const domains = ["api.github.com"];
    const config: AgentConfig = {
      ...DEFAULT_CONFIG,
      security: { domainAllowlist: domains },
    };
    expect(loadDomainAllowlist(config)).toEqual(domains);
  });
});
