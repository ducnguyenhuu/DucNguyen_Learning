/**
 * Token Budget Manager — FR-013
 *
 * Tracks per-run and per-layer token consumption.  The overall budget is the
 * hard limit; per-layer allocations are soft guide-rails that help callers
 * prioritise context loading.
 *
 * Layer percentages (from data-model.md):
 *   L0 repoMap        5%
 *   L1 searchResults 15%
 *   L2 fullFiles     40%
 *   L3 supplementary 10%
 *   reserved         30%
 *
 * Graceful-degradation threshold: 10% of maxTokens remaining.
 */

import { createLayerBudgets } from "../types.js";
import type { LayerBudgets, TokenBudget } from "../types.js";

// ─── Error ────────────────────────────────────────────────────────────────────

export class BudgetExhaustedError extends Error {
  constructor(attempted: number, remaining: number) {
    super(
      `Token budget exhausted: attempted to consume ${attempted} tokens but only ${remaining} remain`,
    );
    this.name = "BudgetExhaustedError";
  }
}

// ─── Manager ──────────────────────────────────────────────────────────────────

export class TokenBudgetManager {
  private readonly maxTokens: number;
  private readonly layerAllocations: LayerBudgets;
  private totalConsumed: number = 0;
  private readonly layerConsumedMap: Record<keyof LayerBudgets, number>;

  /** Graceful-degradation threshold — flag when remaining < 10% of max. */
  private static readonly DEGRADATION_THRESHOLD = 0.1;

  constructor(maxTokens: number) {
    if (maxTokens <= 0) {
      throw new RangeError(`maxTokens must be positive, got ${maxTokens}`);
    }
    this.maxTokens = maxTokens;
    this.layerAllocations = createLayerBudgets(maxTokens);
    this.layerConsumedMap = {
      repoMap: 0,
      searchResults: 0,
      fullFiles: 0,
      supplementary: 0,
      reserved: 0,
    };
  }

  /**
   * Consume `amount` tokens attributed to a specific layer.
   * Throws {@link BudgetExhaustedError} if the total budget would be exceeded.
   */
  consume(layer: keyof LayerBudgets, amount: number): void {
    if (amount < 0) {
      throw new RangeError(`consume amount must be non-negative, got ${amount}`);
    }
    const remaining = this.maxTokens - this.totalConsumed;
    if (amount > remaining) {
      throw new BudgetExhaustedError(amount, remaining);
    }
    this.totalConsumed += amount;
    this.layerConsumedMap[layer] += amount;
  }

  /**
   * Returns an immutable snapshot of the current budget state.
   */
  snapshot(): TokenBudget {
    return {
      maxTokens: this.maxTokens,
      consumed: this.totalConsumed,
      remaining: this.maxTokens - this.totalConsumed,
      layerBudgets: { ...this.layerAllocations },
    };
  }

  /**
   * Returns true when remaining tokens fall below the graceful-degradation
   * threshold (≤ 10% of maxTokens).
   */
  isNearlyExhausted(): boolean {
    const remaining = this.maxTokens - this.totalConsumed;
    return remaining <= this.maxTokens * TokenBudgetManager.DEGRADATION_THRESHOLD;
  }

  /**
   * Returns true if `amount` tokens can be consumed from `layer` without
   * exceeding that layer's soft allocation.
   */
  layerCanAfford(layer: keyof LayerBudgets, amount: number): boolean {
    const layerRemaining = this.layerAllocations[layer] - this.layerConsumedMap[layer];
    return amount <= layerRemaining;
  }

  /**
   * Returns the number of tokens already consumed from the given layer.
   */
  layerConsumed(layer: keyof LayerBudgets): number {
    return this.layerConsumedMap[layer];
  }

  /**
   * Returns the remaining soft budget for a layer (clamped to 0).
   */
  layerRemaining(layer: keyof LayerBudgets): number {
    return Math.max(0, this.layerAllocations[layer] - this.layerConsumedMap[layer]);
  }
}
