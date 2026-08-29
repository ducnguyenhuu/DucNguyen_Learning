import { describe, it, expect, beforeEach } from "vitest";
import { TokenBudgetManager, BudgetExhaustedError } from "../../../src/context/token-budget.js";
import type { LayerBudgets } from "../../../src/types.js";

const MAX_TOKENS = 100_000;
// Layer allocations for MAX_TOKENS = 100_000
const EXPECTED_LAYERS: LayerBudgets = {
  repoMap: 5_000,      // 5%
  searchResults: 15_000, // 15%
  fullFiles: 40_000,   // 40%
  supplementary: 10_000, // 10%
  reserved: 30_000,    // 30%
};

describe("TokenBudgetManager", () => {
  let mgr: TokenBudgetManager;

  beforeEach(() => {
    mgr = new TokenBudgetManager(MAX_TOKENS);
  });

  // ─── Construction ──────────────────────────────────────────────────────────

  describe("constructor", () => {
    it("stores maxTokens correctly", () => {
      expect(mgr.snapshot().maxTokens).toBe(MAX_TOKENS);
    });

    it("starts with consumed = 0", () => {
      expect(mgr.snapshot().consumed).toBe(0);
    });

    it("starts with remaining = maxTokens", () => {
      expect(mgr.snapshot().remaining).toBe(MAX_TOKENS);
    });

    it("computes correct per-layer allocations", () => {
      expect(mgr.snapshot().layerBudgets).toEqual(EXPECTED_LAYERS);
    });

    it("uses Math.floor so allocations never exceed maxTokens", () => {
      // Odd number that won't divide evenly
      const m = new TokenBudgetManager(99_999);
      const lb = m.snapshot().layerBudgets;
      const total =
        lb.repoMap + lb.searchResults + lb.fullFiles + lb.supplementary + lb.reserved;
      expect(total).toBeLessThanOrEqual(99_999);
    });

    it("throws on non-positive maxTokens", () => {
      expect(() => new TokenBudgetManager(0)).toThrow();
      expect(() => new TokenBudgetManager(-1)).toThrow();
    });
  });

  // ─── consume() ─────────────────────────────────────────────────────────────

  describe("consume()", () => {
    it("increases consumed by the given amount", () => {
      mgr.consume("repoMap", 1_000);
      expect(mgr.snapshot().consumed).toBe(1_000);
    });

    it("decreases remaining by the given amount", () => {
      mgr.consume("searchResults", 2_000);
      expect(mgr.snapshot().remaining).toBe(MAX_TOKENS - 2_000);
    });

    it("accumulates multiple consume calls", () => {
      mgr.consume("repoMap", 500);
      mgr.consume("fullFiles", 10_000);
      expect(mgr.snapshot().consumed).toBe(10_500);
      expect(mgr.snapshot().remaining).toBe(MAX_TOKENS - 10_500);
    });

    it("allows consuming exactly the remaining budget", () => {
      // Consume all non-reserved layers; this is fine as long as total <= maxTokens
      mgr.consume("fullFiles", MAX_TOKENS);
      expect(mgr.snapshot().remaining).toBe(0);
    });

    it("throws BudgetExhaustedError when consuming more than remaining", () => {
      mgr.consume("fullFiles", MAX_TOKENS); // drains budget
      expect(() => mgr.consume("repoMap", 1)).toThrow(BudgetExhaustedError);
    });

    it("throws on negative consume amount", () => {
      expect(() => mgr.consume("repoMap", -1)).toThrow();
    });

    it("tracks per-layer consumption — layerConsumed reflects the correct layer", () => {
      mgr.consume("repoMap", 1_000);
      mgr.consume("fullFiles", 5_000);
      expect(mgr.layerConsumed("repoMap")).toBe(1_000);
      expect(mgr.layerConsumed("fullFiles")).toBe(5_000);
      expect(mgr.layerConsumed("searchResults")).toBe(0);
    });
  });

  // ─── snapshot() ────────────────────────────────────────────────────────────

  describe("snapshot()", () => {
    it("returns immutable data — mutating snapshot does not affect manager", () => {
      const snap = mgr.snapshot();
      (snap as { consumed: number }).consumed = 9_999;
      expect(mgr.snapshot().consumed).toBe(0);
    });

    it("remaining is always maxTokens - consumed", () => {
      mgr.consume("searchResults", 7_777);
      const snap = mgr.snapshot();
      expect(snap.remaining).toBe(snap.maxTokens - snap.consumed);
    });
  });

  // ─── isNearlyExhausted() ───────────────────────────────────────────────────

  describe("isNearlyExhausted()", () => {
    it("returns false when budget is untouched", () => {
      expect(mgr.isNearlyExhausted()).toBe(false);
    });

    it("returns false when more than 10% remains", () => {
      // Consume 89% — 11% left → not nearly exhausted
      mgr.consume("fullFiles", Math.floor(MAX_TOKENS * 0.89));
      expect(mgr.isNearlyExhausted()).toBe(false);
    });

    it("returns true when exactly 10% remains", () => {
      // Consume 90%
      mgr.consume("fullFiles", Math.floor(MAX_TOKENS * 0.9));
      expect(mgr.isNearlyExhausted()).toBe(true);
    });

    it("returns true when less than 10% remains", () => {
      // Consume 95%
      mgr.consume("fullFiles", Math.floor(MAX_TOKENS * 0.95));
      expect(mgr.isNearlyExhausted()).toBe(true);
    });
  });

  // ─── layerCanAfford() ──────────────────────────────────────────────────────

  describe("layerCanAfford()", () => {
    it("returns true when nothing has been consumed for the layer", () => {
      expect(mgr.layerCanAfford("repoMap", 1_000)).toBe(true);
    });

    it("returns true for amount equal to layer allocation", () => {
      expect(mgr.layerCanAfford("repoMap", EXPECTED_LAYERS.repoMap)).toBe(true);
    });

    it("returns false for amount exceeding layer allocation", () => {
      expect(mgr.layerCanAfford("repoMap", EXPECTED_LAYERS.repoMap + 1)).toBe(false);
    });

    it("accounts for prior consumption from that layer", () => {
      mgr.consume("repoMap", 3_000);
      // Remaining layer budget = 5_000 - 3_000 = 2_000
      expect(mgr.layerCanAfford("repoMap", 2_000)).toBe(true);
      expect(mgr.layerCanAfford("repoMap", 2_001)).toBe(false);
    });
  });

  // ─── layerRemaining() ──────────────────────────────────────────────────────

  describe("layerRemaining()", () => {
    it("returns full allocation initially", () => {
      expect(mgr.layerRemaining("fullFiles")).toBe(EXPECTED_LAYERS.fullFiles);
    });

    it("decreases after consuming from that layer", () => {
      mgr.consume("fullFiles", 10_000);
      expect(mgr.layerRemaining("fullFiles")).toBe(EXPECTED_LAYERS.fullFiles - 10_000);
    });

    it("clamps to 0 when over-consumed (cross-layer overflow)", () => {
      // Over-consume one layer (allowed in our model since total budget is the hard limit)
      // If per-layer overspend is tracked, remaining should not go negative
      mgr.consume("repoMap", EXPECTED_LAYERS.repoMap + 1_000);
      expect(mgr.layerRemaining("repoMap")).toBe(0);
    });

    it("is unaffected by consumption from a different layer", () => {
      mgr.consume("searchResults", 5_000);
      expect(mgr.layerRemaining("fullFiles")).toBe(EXPECTED_LAYERS.fullFiles);
    });
  });
});
