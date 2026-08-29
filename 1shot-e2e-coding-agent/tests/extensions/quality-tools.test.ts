/**
 * tests/extensions/quality-tools.test.ts — T049
 *
 * Contract tests for the quality-tools Pi Extension factory (T050).
 * Verifies registration shape, options validation, and expected tool list.
 *
 * These tests will FAIL until T050 implements extensions/quality-tools.ts.
 * That is expected — TDD: write tests first, then implement.
 */

import { describe, it, expect } from "vitest";

import {
  createQualityToolsExtension,
  type QualityToolsOptions,
  type QualityToolsExtension,
} from "../../extensions/quality-tools.js";

// ─── Helpers ──────────────────────────────────────────────────────────────────

const BASE_OPTIONS: QualityToolsOptions = {
  workspacePath: "/workspace/test-repo",
  testCommand: "npm test",
  lintCommand: "npm run lint",
};

// ─── createQualityToolsExtension ──────────────────────────────────────────────

describe("createQualityToolsExtension()", () => {
  // ── Factory behaviour ─────────────────────────────────────────────────────

  it("returns a QualityToolsExtension without throwing", () => {
    expect(() => createQualityToolsExtension(BASE_OPTIONS)).not.toThrow();
  });

  it("is a synchronous factory function", () => {
    const result = createQualityToolsExtension(BASE_OPTIONS);
    expect(result).toBeDefined();
    expect(typeof (result as unknown as { then?: unknown }).then).not.toBe("function");
  });

  // ── QualityToolsOptions — interface contract ───────────────────────────────

  it("contract: options require workspacePath", () => {
    const opts: QualityToolsOptions = {
      workspacePath: "/workspace",
      testCommand: "npm test",
      lintCommand: "npm run lint",
    };
    expect(typeof opts.workspacePath).toBe("string");
  });

  it("contract: options require testCommand", () => {
    const opts: QualityToolsOptions = {
      workspacePath: "/workspace",
      testCommand: "vitest run",
      lintCommand: "eslint .",
    };
    expect(typeof opts.testCommand).toBe("string");
  });

  it("contract: options require lintCommand", () => {
    const opts: QualityToolsOptions = {
      workspacePath: "/workspace",
      testCommand: "npm test",
      lintCommand: "npm run lint",
    };
    expect(typeof opts.lintCommand).toBe("string");
  });
});

// ─── QualityToolsExtension — factory output ───────────────────────────────────

describe("QualityToolsExtension — factory output (T050)", () => {
  it("returns name 'quality-tools'", () => {
    const ext = createQualityToolsExtension(BASE_OPTIONS);
    expect(ext.name).toBe("quality-tools");
  });

  it("returns a tools string array", () => {
    const ext = createQualityToolsExtension(BASE_OPTIONS);
    expect(Array.isArray(ext.tools)).toBe(true);
  });

  it("registers exactly two tools", () => {
    const ext = createQualityToolsExtension(BASE_OPTIONS);
    expect(ext.tools).toHaveLength(2);
  });

  it("registers run_test tool", () => {
    const ext = createQualityToolsExtension(BASE_OPTIONS);
    expect(ext.tools).toContain("run_test");
  });

  it("registers run_lint tool", () => {
    const ext = createQualityToolsExtension(BASE_OPTIONS);
    expect(ext.tools).toContain("run_lint");
  });
});

// ─── ToolDefinition shape ─────────────────────────────────────────────────────

describe("QualityToolsExtension — toolDefinitions shape (T050)", () => {
  it("returns toolDefinitions array", () => {
    const ext = createQualityToolsExtension(BASE_OPTIONS);
    expect(Array.isArray(ext.toolDefinitions)).toBe(true);
  });

  it("toolDefinitions has two entries", () => {
    const ext = createQualityToolsExtension(BASE_OPTIONS);
    expect(ext.toolDefinitions).toHaveLength(2);
  });

  it("run_test tool definition has name 'run_test'", () => {
    const ext = createQualityToolsExtension(BASE_OPTIONS);
    const runTest = ext.toolDefinitions?.find((t) => t.name === "run_test");
    expect(runTest).toBeDefined();
  });

  it("run_lint tool definition has name 'run_lint'", () => {
    const ext = createQualityToolsExtension(BASE_OPTIONS);
    const runLint = ext.toolDefinitions?.find((t) => t.name === "run_lint");
    expect(runLint).toBeDefined();
  });

  it("run_test tool has a description string", () => {
    const ext = createQualityToolsExtension(BASE_OPTIONS);
    const runTest = ext.toolDefinitions?.find((t) => t.name === "run_test");
    expect(typeof runTest?.description).toBe("string");
    expect((runTest?.description ?? "").length).toBeGreaterThan(0);
  });

  it("run_lint tool has a description string", () => {
    const ext = createQualityToolsExtension(BASE_OPTIONS);
    const runLint = ext.toolDefinitions?.find((t) => t.name === "run_lint");
    expect(typeof runLint?.description).toBe("string");
    expect((runLint?.description ?? "").length).toBeGreaterThan(0);
  });

  it("run_test tool has an execute function", () => {
    const ext = createQualityToolsExtension(BASE_OPTIONS);
    const runTest = ext.toolDefinitions?.find((t) => t.name === "run_test");
    expect(typeof runTest?.execute).toBe("function");
  });

  it("run_lint tool has an execute function", () => {
    const ext = createQualityToolsExtension(BASE_OPTIONS);
    const runLint = ext.toolDefinitions?.find((t) => t.name === "run_lint");
    expect(typeof runLint?.execute).toBe("function");
  });

  it("run_test tool has parameters schema", () => {
    const ext = createQualityToolsExtension(BASE_OPTIONS);
    const runTest = ext.toolDefinitions?.find((t) => t.name === "run_test");
    expect(runTest?.parameters).toBeDefined();
  });

  it("run_lint tool has parameters schema", () => {
    const ext = createQualityToolsExtension(BASE_OPTIONS);
    const runLint = ext.toolDefinitions?.find((t) => t.name === "run_lint");
    expect(runLint?.parameters).toBeDefined();
  });
});

// ─── Typed export contract ────────────────────────────────────────────────────

describe("QualityToolsExtension — TypeScript contract (T050)", () => {
  it("QualityToolsExtension has name, tools, and toolDefinitions fields", () => {
    const ext: QualityToolsExtension = createQualityToolsExtension(BASE_OPTIONS);
    expect(typeof ext.name).toBe("string");
    expect(Array.isArray(ext.tools)).toBe(true);
    expect(Array.isArray(ext.toolDefinitions)).toBe(true);
  });
});
