/**
 * Unit tests for path validation — tests/unit/security/path-validator.test.ts
 *
 * These tests define the CONTRACT for src/security/path-validator.ts.
 * Written TDD-first — will fail until T013 creates the implementation.
 *
 * What is tested (FR-019):
 *  - isPathAllowed(): accepts paths inside the repo root
 *  - isPathAllowed(): rejects paths outside the repo root
 *  - isPathAllowed(): rejects directory traversal (../) attempts
 *  - isPathAllowed(): rejects absolute paths outside repo root
 *  - assertPathAllowed(): throws PathValidationError on violation
 *  - assertPathAllowed(): resolves and returns the absolute path on success
 *  - Symlink handling: symlinks that resolve outside the repo are rejected
 *  - Edge cases: repo root itself, trailing slashes, empty strings
 */

import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { mkdir, writeFile, rm, symlink } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { realpathSync } from "node:fs";
import {
  isPathAllowed,
  assertPathAllowed,
  PathValidationError,
} from "../../../src/security/path-validator.js";

// ─── Helpers ──────────────────────────────────────────────────────────────────

let repoRoot: string;
let outsideDir: string;

beforeEach(async () => {
  const base = join(tmpdir(), `pv-test-${Date.now()}`);
  repoRoot = join(base, "repo");
  outsideDir = join(base, "outside");
  await mkdir(join(repoRoot, "src"), { recursive: true });
  await mkdir(outsideDir, { recursive: true });
  await writeFile(join(repoRoot, "README.md"), "# test");
  await writeFile(join(repoRoot, "src", "index.ts"), "export {};");
  await writeFile(join(outsideDir, "secret.txt"), "secret");
});

afterEach(async () => {
  const base = repoRoot.replace(/\/repo$/, "");
  await rm(base, { recursive: true, force: true });
});

// ─── isPathAllowed() ──────────────────────────────────────────────────────────

describe("isPathAllowed()", () => {
  it("returns true for a file directly inside the repo root", () => {
    expect(isPathAllowed(join(repoRoot, "README.md"), repoRoot)).toBe(true);
  });

  it("returns true for a file in a subdirectory inside the repo", () => {
    expect(isPathAllowed(join(repoRoot, "src", "index.ts"), repoRoot)).toBe(true);
  });

  it("returns true for the repo root itself", () => {
    expect(isPathAllowed(repoRoot, repoRoot)).toBe(true);
  });

  it("returns true for a relative path that resolves inside the repo", () => {
    // A relative path passed with repoRoot as cwd baseline
    expect(isPathAllowed(join(repoRoot, "src/../README.md"), repoRoot)).toBe(true);
  });

  it("returns false for a path outside the repo root", () => {
    expect(isPathAllowed(join(outsideDir, "secret.txt"), repoRoot)).toBe(false);
  });

  it("returns false for a path with directory traversal escaping the repo", () => {
    expect(isPathAllowed(join(repoRoot, "..", "outside", "secret.txt"), repoRoot)).toBe(false);
  });

  it("returns false for the root filesystem path /", () => {
    expect(isPathAllowed("/", repoRoot)).toBe(false);
  });

  it("returns false for /etc/passwd", () => {
    expect(isPathAllowed("/etc/passwd", repoRoot)).toBe(false);
  });

  it("returns false for an empty string", () => {
    expect(isPathAllowed("", repoRoot)).toBe(false);
  });

  it("returns false when repoRoot itself is empty", () => {
    expect(isPathAllowed(join(repoRoot, "file.ts"), "")).toBe(false);
  });
});

// ─── assertPathAllowed() ─────────────────────────────────────────────────────

describe("assertPathAllowed()", () => {
  it("returns the resolved absolute path for an allowed file", () => {
    const result = assertPathAllowed(join(repoRoot, "README.md"), repoRoot);
    expect(result).toBe(realpathSync(join(repoRoot, "README.md")));
  });

  it("resolves relative path components (../) before validating", () => {
    // README.md is actually inside the repo even with spurious ../ that cancels out
    const result = assertPathAllowed(
      join(repoRoot, "src", "..", "README.md"),
      repoRoot,
    );
    expect(result).toBe(realpathSync(join(repoRoot, "README.md")));
  });

  it("throws PathValidationError for a path outside the repo", () => {
    expect(() =>
      assertPathAllowed(join(outsideDir, "secret.txt"), repoRoot),
    ).toThrow(PathValidationError);
  });

  it("throws PathValidationError for a directory traversal attempt", () => {
    expect(() =>
      assertPathAllowed(join(repoRoot, "..", "outside", "secret.txt"), repoRoot),
    ).toThrow(PathValidationError);
  });

  it("throws PathValidationError for /etc/passwd", () => {
    expect(() => assertPathAllowed("/etc/passwd", repoRoot)).toThrow(
      PathValidationError,
    );
  });

  it("includes the attempted path in the error message", () => {
    const badPath = "/etc/shadow";
    try {
      assertPathAllowed(badPath, repoRoot);
      expect.fail("should have thrown");
    } catch (err) {
      expect(err).toBeInstanceOf(PathValidationError);
      expect((err as PathValidationError).message).toContain(badPath);
    }
  });

  it("includes the repo root in the error message", () => {
    try {
      assertPathAllowed("/etc/shadow", repoRoot);
      expect.fail("should have thrown");
    } catch (err) {
      expect((err as PathValidationError).message).toContain(repoRoot);
    }
  });

  it("throws PathValidationError for an empty string path", () => {
    expect(() => assertPathAllowed("", repoRoot)).toThrow(PathValidationError);
  });
});

// ─── PathValidationError ──────────────────────────────────────────────────────

describe("PathValidationError", () => {
  it("is an instance of Error", () => {
    const err = new PathValidationError("bad path", "/repo");
    expect(err).toBeInstanceOf(Error);
  });

  it("has the correct name", () => {
    const err = new PathValidationError("bad path", "/repo");
    expect(err.name).toBe("PathValidationError");
  });

  it("exposes attemptedPath and repoRoot properties", () => {
    const err = new PathValidationError("/etc/passwd", "/workspace/repo");
    expect(err.attemptedPath).toBe("/etc/passwd");
    expect(err.repoRoot).toBe("/workspace/repo");
  });
});

// ─── Symlink handling ─────────────────────────────────────────────────────────

describe("symlink handling", () => {
  it("rejects a symlink inside the repo that points outside the repo", async () => {
    const linkPath = join(repoRoot, "evil-link");
    await symlink(join(outsideDir, "secret.txt"), linkPath);

    // isPathAllowed uses real-path resolution — the link itself is inside
    // repo but its target is outside, so it must be rejected
    expect(isPathAllowed(linkPath, repoRoot)).toBe(false);
  });

  it("accepts a symlink that points to a file inside the repo", async () => {
    const linkPath = join(repoRoot, "safe-link");
    await symlink(join(repoRoot, "README.md"), linkPath);

    expect(isPathAllowed(linkPath, repoRoot)).toBe(true);
  });
});
