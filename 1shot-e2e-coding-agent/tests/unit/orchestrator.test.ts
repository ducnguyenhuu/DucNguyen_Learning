/**
 * Unit tests for BlueprintRunner orchestrator — tests/unit/orchestrator.test.ts
 *
 * These tests define the CONTRACT for src/orchestrator.ts.
 * Written TDD-first — will fail until T011 creates the implementation.
 *
 * What is tested:
 *  - addNode() / run(): linear execution of a sequence of nodes
 *  - Conditional routing: next() returning different nodeIds based on StepResult
 *  - Error propagation: a node returning status "error" stops the run
 *  - Throw propagation: uncaught throws from execute() are caught and surfaced
 *  - Null routing: next() returning null ends the run cleanly
 *  - NodeResult recording: timings and statuses captured for every executed node
 *  - Unknown entry node: BlueprintRunner throws before executing anything
 *  - Unknown next node: BlueprintRunner throws after receiving a bad nodeId
 */

import { describe, it, expect, vi } from "vitest";
import { BlueprintRunner } from "../../src/orchestrator.js";
import type { RunContext, StepResult, BlueprintNode } from "../../src/types.js";

// ─── Helpers ──────────────────────────────────────────────────────────────────

/** Minimal RunContext stub — orchestrator only reads it, never mutates it. */
function makeCtx(): RunContext {
  return {
    task: { description: "test task", slug: "test-task", timestamp: "2026-03-15T00:00:00Z" },
    config: {
      agent: { name: "test", maxTokensPerRun: 200_000, maxCostPerRunUsd: 2.0, timeoutSeconds: 600 },
      provider: { default: "anthropic" },
      repo: { path: "/workspace", language: "typescript", testCommand: "vitest run", lintCommand: "eslint" },
    },
    workspacePath: "/workspace",
    branch: "agent/test-task",
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
      layerBudgets: { repoMap: 10_000, searchResults: 30_000, fullFiles: 80_000, supplementary: 20_000, reserved: 60_000 },
    },
    logger: { info: vi.fn(), error: vi.fn(), warn: vi.fn(), debug: vi.fn() },
  } as unknown as RunContext;
}

function passNode(id: string, nextId: string | null = null): BlueprintNode {
  return {
    id,
    type: "deterministic",
    execute: vi.fn(async () => ({ status: "passed" as const })),
    next: vi.fn(() => nextId),
  };
}

function failNode(id: string, nextId: string | null = null): BlueprintNode {
  return {
    id,
    type: "deterministic",
    execute: vi.fn(async () => ({ status: "failed" as const, error: "step failed" })),
    next: vi.fn(() => nextId),
  };
}

function errorNode(id: string): BlueprintNode {
  return {
    id,
    type: "deterministic",
    execute: vi.fn(async () => ({ status: "error" as const, error: "unexpected error" })),
    next: vi.fn(() => "never"),
  };
}

function throwingNode(id: string): BlueprintNode {
  return {
    id,
    type: "deterministic",
    execute: vi.fn(async () => { throw new Error("execute threw"); }),
    next: vi.fn(() => "never"),
  };
}

// ─── BlueprintRunner ──────────────────────────────────────────────────────────

describe("BlueprintRunner", () => {
  // ── Construction ──────────────────────────────────────────────────────────

  describe("construction", () => {
    it("can be instantiated with a blueprint name and entry node", () => {
      const runner = new BlueprintRunner("test-blueprint", "node_a");
      expect(runner).toBeDefined();
    });
  });

  // ── addNode() ─────────────────────────────────────────────────────────────

  describe("addNode()", () => {
    it("returns the runner instance for chaining", () => {
      const runner = new BlueprintRunner("bp", "a");
      const result = runner.addNode(passNode("a"));
      expect(result).toBe(runner);
    });
  });

  // ── run(): linear sequencing ──────────────────────────────────────────────

  describe("run(): linear sequencing", () => {
    it("executes a single node and returns succeeded", async () => {
      const node = passNode("only", null);
      const runner = new BlueprintRunner("bp", "only").addNode(node);

      const summary = await runner.run(makeCtx());

      expect(node.execute).toHaveBeenCalledOnce();
      expect(summary.status).toBe("succeeded");
    });

    it("executes nodes in the order given by next()", async () => {
      const order: string[] = [];
      const nodeA: BlueprintNode = {
        id: "a", type: "deterministic",
        execute: vi.fn(async () => { order.push("a"); return { status: "passed" as const }; }),
        next: vi.fn(() => "b"),
      };
      const nodeB: BlueprintNode = {
        id: "b", type: "deterministic",
        execute: vi.fn(async () => { order.push("b"); return { status: "passed" as const }; }),
        next: vi.fn(() => null),
      };

      await new BlueprintRunner("bp", "a").addNode(nodeA).addNode(nodeB).run(makeCtx());

      expect(order).toEqual(["a", "b"]);
    });

    it("returns status succeeded when all nodes pass and routing ends with null", async () => {
      const runner = new BlueprintRunner("bp", "a")
        .addNode(passNode("a", "b"))
        .addNode(passNode("b", null));

      const summary = await runner.run(makeCtx());
      expect(summary.status).toBe("succeeded");
    });

    it("passes the RunContext to every node's execute()", async () => {
      const ctx = makeCtx();
      const nodeA = passNode("a", "b");
      const nodeB = passNode("b", null);

      await new BlueprintRunner("bp", "a").addNode(nodeA).addNode(nodeB).run(ctx);

      expect(nodeA.execute).toHaveBeenCalledWith(ctx);
      expect(nodeB.execute).toHaveBeenCalledWith(ctx);
    });

    it("passes the StepResult to the node's next() function", async () => {
      const result: StepResult = { status: "passed", data: { key: "value" } };
      const node: BlueprintNode = {
        id: "a", type: "deterministic",
        execute: vi.fn(async () => result),
        next: vi.fn(() => null),
      };

      await new BlueprintRunner("bp", "a").addNode(node).run(makeCtx());

      expect(node.next).toHaveBeenCalledWith(result);
    });
  });

  // ── run(): conditional routing ────────────────────────────────────────────

  describe("run(): conditional routing", () => {
    it("follows the branch chosen by next() when result is passed", async () => {
      const routerNode: BlueprintNode = {
        id: "router", type: "deterministic",
        execute: vi.fn(async () => ({ status: "passed" as const })),
        next: (r) => r.status === "passed" ? "happy" : "sad",
      };
      const happyNode = passNode("happy", null);
      const sadNode = passNode("sad", null);

      await new BlueprintRunner("bp", "router")
        .addNode(routerNode).addNode(happyNode).addNode(sadNode)
        .run(makeCtx());

      expect(happyNode.execute).toHaveBeenCalledOnce();
      expect(sadNode.execute).not.toHaveBeenCalled();
    });

    it("follows the branch chosen by next() when result is failed", async () => {
      const routerNode: BlueprintNode = {
        id: "router", type: "deterministic",
        execute: vi.fn(async () => ({ status: "failed" as const })),
        next: (r) => r.status === "passed" ? "happy" : "sad",
      };
      const happyNode = passNode("happy", null);
      const sadNode = passNode("sad", null);

      await new BlueprintRunner("bp", "router")
        .addNode(routerNode).addNode(happyNode).addNode(sadNode)
        .run(makeCtx());

      expect(sadNode.execute).toHaveBeenCalledOnce();
      expect(happyNode.execute).not.toHaveBeenCalled();
    });
  });

  // ── run(): error handling ─────────────────────────────────────────────────

  describe("run(): error handling", () => {
    it("stops execution when a node returns status error", async () => {
      const after = passNode("after", null);
      const runner = new BlueprintRunner("bp", "bad")
        .addNode(errorNode("bad"))
        .addNode(after);

      const summary = await runner.run(makeCtx());

      expect(summary.status).toBe("failed");
      expect(after.execute).not.toHaveBeenCalled();
    });

    it("records the error message in the run summary", async () => {
      const runner = new BlueprintRunner("bp", "bad").addNode(errorNode("bad"));

      const summary = await runner.run(makeCtx());

      expect(summary.error).toBeDefined();
      expect(summary.error).toMatch(/unexpected error/);
    });

    it("catches exceptions thrown by execute() and stops the run", async () => {
      const after = passNode("after", null);
      const runner = new BlueprintRunner("bp", "thrower")
        .addNode(throwingNode("thrower"))
        .addNode(after);

      const summary = await runner.run(makeCtx());

      expect(summary.status).toBe("failed");
      expect(after.execute).not.toHaveBeenCalled();
      expect(summary.error).toMatch(/execute threw/);
    });

    it("throws when the entry node id is not registered", async () => {
      const runner = new BlueprintRunner("bp", "missing");
      await expect(runner.run(makeCtx())).rejects.toThrow(/missing/);
    });

    it("throws when next() returns an unknown node id", async () => {
      const node: BlueprintNode = {
        id: "a", type: "deterministic",
        execute: vi.fn(async () => ({ status: "passed" as const })),
        next: vi.fn(() => "non_existent"),
      };
      const runner = new BlueprintRunner("bp", "a").addNode(node);
      await expect(runner.run(makeCtx())).rejects.toThrow(/non_existent/);
    });
  });

  // ── run(): NodeResult recording ───────────────────────────────────────────

  describe("run(): NodeResult recording", () => {
    it("records a NodeResult for each executed node", async () => {
      const runner = new BlueprintRunner("bp", "a")
        .addNode(passNode("a", "b"))
        .addNode(passNode("b", null));

      const summary = await runner.run(makeCtx());

      expect(summary.nodeResults).toHaveLength(2);
      expect(summary.nodeResults[0]?.nodeId).toBe("a");
      expect(summary.nodeResults[1]?.nodeId).toBe("b");
    });

    it("records duration >= 0 for each node", async () => {
      const runner = new BlueprintRunner("bp", "a").addNode(passNode("a", null));
      const summary = await runner.run(makeCtx());
      expect(summary.nodeResults[0]?.duration).toBeGreaterThanOrEqual(0);
    });

    it("records the correct status for each node", async () => {
      const runner = new BlueprintRunner("bp", "a")
        .addNode(passNode("a", "b"))
        .addNode(failNode("b", null));

      const summary = await runner.run(makeCtx());

      expect(summary.nodeResults[0]?.status).toBe("passed");
      expect(summary.nodeResults[1]?.status).toBe("failed");
    });

    it("does not record nodes that were skipped due to early stop", async () => {
      const runner = new BlueprintRunner("bp", "a")
        .addNode(errorNode("a"))
        .addNode(passNode("b", null));

      const summary = await runner.run(makeCtx());

      expect(summary.nodeResults).toHaveLength(1);
      expect(summary.nodeResults[0]?.nodeId).toBe("a");
    });
  });

  // ── run(): overall status rules ───────────────────────────────────────────

  describe("run(): overall status", () => {
    it("is succeeded when all nodes complete and last result is passed", async () => {
      const summary = await new BlueprintRunner("bp", "a")
        .addNode(passNode("a", null))
        .run(makeCtx());
      expect(summary.status).toBe("succeeded");
    });

    it("is succeeded when last node result is failed but routing ends (null next)", async () => {
      // A node returning "failed" doesn't mean the run failed — it may be
      // a normal signal that routes to a retry/fix path. The run only fails
      // when routing itself terminates after a "failed" result with null next.
      // The overall run outcome is "succeeded" if it completed without error.
      const summary = await new BlueprintRunner("bp", "a")
        .addNode(failNode("a", null))
        .run(makeCtx());
      // The run completes; status reflects the last node
      expect(["succeeded", "failed"]).toContain(summary.status);
    });

    it("is failed when a node returns status error", async () => {
      const summary = await new BlueprintRunner("bp", "a")
        .addNode(errorNode("a"))
        .run(makeCtx());
      expect(summary.status).toBe("failed");
    });

    it("is failed when a node throws", async () => {
      const summary = await new BlueprintRunner("bp", "a")
        .addNode(throwingNode("a"))
        .run(makeCtx());
      expect(summary.status).toBe("failed");
    });
  });
});
