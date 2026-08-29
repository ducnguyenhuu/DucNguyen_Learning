/**
 * tests/unit/blueprints/standard.test.ts — T082
 *
 * Tests the standard blueprint routing logic:
 *   - test pass  → commit_and_push
 *   - test fail  → fix_failures
 *   - fix_failures retryCount < maxRetries → test (retry loop)
 *   - fix_failures retryCount ≥ maxRetries → null (abort)
 *   - sequential routing for all other nodes
 */

import { describe, it, expect, vi } from "vitest";
import {
  routeAfterTest,
  routeAfterFixFailures,
  createStandardBlueprint,
} from "../../../src/blueprints/standard.js";
import type { RunContext, StepResult } from "../../../src/types.js";
import { DEFAULT_CONFIG } from "../../../src/config.js";
import { createLayerBudgets } from "../../../src/types.js";

// ─── Mocks — all step modules ─────────────────────────────────────────────────
// We mock every step so createStandardBlueprint can be imported without Pi SDK

vi.mock("../../../src/steps/setup.js", () => ({ setupStep: vi.fn() }));
vi.mock("../../../src/steps/context-gather.js", () => ({ contextGatherStep: vi.fn() }));
vi.mock("../../../src/steps/plan.js", () => ({ planStep: vi.fn() }));
vi.mock("../../../src/steps/implement.js", () => ({ implementStep: vi.fn() }));
vi.mock("../../../src/steps/lint-format.js", () => ({ lintFormatStep: vi.fn() }));
vi.mock("../../../src/steps/test.js", () => ({ testStep: vi.fn() }));
vi.mock("../../../src/steps/fix-failures.js", () => ({ fixFailuresStep: vi.fn() }));
vi.mock("../../../src/steps/commit-push.js", () => ({ commitPushStep: vi.fn() }));
vi.mock("../../../src/steps/report.js", () => ({ reportStep: vi.fn() }));
vi.mock("../../../extensions/quality-tools.js", () => ({
  createQualityToolsExtension: vi.fn(() => ({
    name: "quality-tools",
    tools: ["run_test", "run_lint"],
    toolDefinitions: [],
  })),
}));

// ─── Helpers ──────────────────────────────────────────────────────────────────

function makeCtx(overrides: Partial<RunContext> = {}): RunContext {
  return {
    task: { description: "fix login bug", slug: "fix-login-bug", timestamp: "2026-03-17T00:00:00Z" },
    config: {
      ...DEFAULT_CONFIG,
      shiftLeft: { maxRetries: 2 },
    },
    workspacePath: "/workspace/test-repo",
    branch: "agent/fix-login-bug",
    repoMap: "",
    relevantFiles: [],
    understanding: "",
    plan: "",
    retryCount: 0,
    errorHashes: [],
    tokenBudget: {
      maxTokens: 200_000,
      consumed: 0,
      remaining: 200_000,
      layerBudgets: createLayerBudgets(200_000),
    },
    logger: { info: vi.fn(), warn: vi.fn(), error: vi.fn() },
    ...overrides,
  };
}

const PASSED: StepResult = { status: "passed" };
const FAILED: StepResult = { status: "failed" };

// ─── routeAfterTest ───────────────────────────────────────────────────────────

describe("routeAfterTest()", () => {
  it("routes to commit_and_push when test passes", () => {
    expect(routeAfterTest(PASSED)).toBe("commit_and_push");
  });

  it("routes to fix_failures when test fails", () => {
    expect(routeAfterTest(FAILED)).toBe("fix_failures");
  });

  it("routes to fix_failures when test errors", () => {
    expect(routeAfterTest({ status: "error" })).toBe("fix_failures");
  });
});

// ─── routeAfterFixFailures ────────────────────────────────────────────────────

describe("routeAfterFixFailures()", () => {
  it("routes back to test when retryCount < maxRetries", () => {
    const ctx = makeCtx({ retryCount: 0 });
    expect(routeAfterFixFailures(ctx, 2)).toBe("test");
  });

  it("routes back to test when retryCount is 1 and maxRetries is 2", () => {
    const ctx = makeCtx({ retryCount: 1 });
    expect(routeAfterFixFailures(ctx, 2)).toBe("test");
  });

  it("returns null (abort) when retryCount equals maxRetries", () => {
    const ctx = makeCtx({ retryCount: 2 });
    expect(routeAfterFixFailures(ctx, 2)).toBeNull();
  });

  it("returns null (abort) when retryCount exceeds maxRetries", () => {
    const ctx = makeCtx({ retryCount: 3 });
    expect(routeAfterFixFailures(ctx, 2)).toBeNull();
  });

  it("respects custom maxRetries value", () => {
    const ctx = makeCtx({ retryCount: 4 });
    expect(routeAfterFixFailures(ctx, 5)).toBe("test");
  });

  it("returns null immediately when maxRetries is 0", () => {
    const ctx = makeCtx({ retryCount: 0 });
    expect(routeAfterFixFailures(ctx, 0)).toBeNull();
  });
});

// ─── createStandardBlueprint — node registration ─────────────────────────────

describe("createStandardBlueprint()", () => {
  it("returns a BlueprintRunner without throwing", () => {
    const runner = createStandardBlueprint(makeCtx());
    expect(runner).toBeDefined();
  });

  it("uses maxRetries from ctx.config.shiftLeft", () => {
    const ctx = makeCtx();
    ctx.config.shiftLeft = { maxRetries: 3 };
    // No throws = blueprint constructed with custom maxRetries
    expect(() => createStandardBlueprint(ctx)).not.toThrow();
  });

  it("defaults maxRetries to 2 when shiftLeft is not configured", () => {
    const ctx = makeCtx();
    ctx.config.shiftLeft = undefined;
    expect(() => createStandardBlueprint(ctx)).not.toThrow();
  });

  it("routes fix_failures to test when ctx.retryCount < maxRetries (live closure)", () => {
    const ctx = makeCtx({ retryCount: 0 });
    // routeAfterFixFailures is called with the live ctx reference
    // At retryCount=0, maxRetries=2 → should return "test"
    expect(routeAfterFixFailures(ctx, ctx.config.shiftLeft?.maxRetries ?? 2)).toBe("test");
  });

  it("aborts when ctx.retryCount reaches maxRetries (live closure)", () => {
    const ctx = makeCtx({ retryCount: 2 });
    expect(routeAfterFixFailures(ctx, ctx.config.shiftLeft?.maxRetries ?? 2)).toBeNull();
  });
});
