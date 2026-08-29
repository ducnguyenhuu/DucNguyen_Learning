/**
 * src/orchestrator.ts — BlueprintRunner (Architecture Decision D1)
 *
 * Sequences blueprint nodes by repeatedly:
 *   1. Executing the current node's execute(ctx) function
 *   2. Calling node.next(result) to get the next node ID (or null to stop)
 *
 * Each node is either:
 *  - "deterministic": a plain TypeScript function (lint, test, git, etc.)
 *  - "agent": a Pi SDK session (context-gather, plan, implement, fix-failures)
 *
 * Why a simple while-loop instead of a framework:
 *   The workflow has exactly one conditional branch (test pass/fail).
 *   A ~150 LOC while-loop is simpler, easier to debug, and has no external deps.
 *   See plan.md D1 for full rationale.
 *
 * T072 additions: graceful error fallback routing + logger integration
 * T073 additions: per-run AbortController + per-node timeout wrapping
 */

import type { RunContext, BlueprintNode, StepResult, NodeResult } from "./types.js";

// ─── RunSummary ───────────────────────────────────────────────────────────────

export interface RunSummary {
  /** "succeeded" if the run completed without error, "failed" otherwise. */
  status: "succeeded" | "failed";
  /** Human-readable error message when status is "failed". */
  error?: string;
  /** Results for each node that was executed (in execution order). */
  nodeResults: NodeResult[];
  /** Total wall-clock duration of the run in milliseconds. */
  durationMs: number;
}

// ─── Logger helper (T072) ─────────────────────────────────────────────────────

/** Safely call logger.error() without coupling to a concrete logger type. */
function safeLogError(logger: unknown, message: string): void {
  if (
    logger !== null &&
    typeof logger === "object" &&
    "error" in logger &&
    typeof (logger as { error: unknown }).error === "function"
  ) {
    (logger as { error: (msg: string) => void }).error(message);
  }
}

// ─── BlueprintRunner ──────────────────────────────────────────────────────────

export class BlueprintRunner {
  private readonly _name: string;
  private readonly _entryNodeId: string;
  private readonly _nodes = new Map<string, BlueprintNode>();
  /** Node ID to route to when any other node fails/throws (T072). */
  private _errorFallbackNodeId?: string;
  /** Per-node timeout in ms, 0 = disabled (T073). */
  private _nodeTimeoutMs: number = 0;

  constructor(name: string, entryNodeId: string) {
    this._name = name;
    this._entryNodeId = entryNodeId;
  }

  /**
   * Register a node with the runner.
   * Returns `this` for method chaining: runner.addNode(a).addNode(b).run(ctx)
   */
  addNode(node: BlueprintNode): this {
    this._nodes.set(node.id, node);
    return this;
  }

  /**
   * Register a fallback node to route to when any other node throws or returns
   * status "error". Used to ensure the report step always runs (T072).
   */
  setErrorFallback(nodeId: string): this {
    this._errorFallbackNodeId = nodeId;
    return this;
  }

  /**
   * Set a per-node execution timeout in milliseconds.
   * When elapsed, a rejection is raced against the execute() promise (T073).
   * Set to 0 to disable (default).
   */
  setNodeTimeout(ms: number): this {
    this._nodeTimeoutMs = ms;
    return this;
  }

  /**
   * Execute the blueprint starting from the entry node.
   *
   * Execution model:
   *  1. Create a per-run AbortController from config.agent.timeoutSeconds (T073).
   *  2. Look up the current node. Throw if not found.
   *  3. Call execute(ctx) wrapped in a per-node timeout race (T073).
   *  4. If result.status is "error" or execute() throws:
   *       a. Log to ctx.logger (T072)
   *       b. If errorFallback is set and not already in fallback, route there (T072)
   *       c. Otherwise return failed immediately.
   *  5. Call node.next(result) to get the next node ID.
   *  6. If next returns null, stop → succeeded.
   *  7. If next returns an unknown ID, throw.
   *  8. Repeat from step 2 with the new node ID.
   */
  async run(ctx: RunContext): Promise<RunSummary> {
    const runStart = Date.now();
    const nodeResults: NodeResult[] = [];

    // ── T073: Per-run timeout via AbortController ─────────────────────────────
    const timeoutSeconds = ctx.config.agent?.timeoutSeconds ?? 0;
    const runAbort = new AbortController();
    let runTimeoutId: ReturnType<typeof setTimeout> | undefined;

    if (timeoutSeconds > 0) {
      runTimeoutId = setTimeout(() => {
        runAbort.abort("run-timeout");
      }, timeoutSeconds * 1000);

      // Prevent the timer from keeping the Node.js process alive after the run
      if (typeof runTimeoutId === "object" && "unref" in runTimeoutId) {
        (runTimeoutId as { unref(): void }).unref();
      }
    }

    // Expose the signal on RunContext so step functions can respect it
    (ctx as RunContext & { abortSignal: AbortSignal }).abortSignal = runAbort.signal;

    try {
      // Validate entry node exists before starting
      if (!this._nodes.has(this._entryNodeId)) {
        throw new Error(
          `BlueprintRunner "${this._name}": entry node "${this._entryNodeId}" is not registered`,
        );
      }

      let currentNodeId: string | null = this._entryNodeId;
      /** Prevent the error fallback from recursively routing to itself. */
      let inErrorFallback = false;
      /** Frozen error info from before routing to fallback (for final status). */
      let fallbackError: string | undefined;

      while (currentNodeId !== null) {
        // ── Check per-run abort before each node (T073) ─────────────────────
        if (runAbort.signal.aborted) {
          return {
            status: "failed",
            error: `Run exceeded timeout of ${timeoutSeconds}s`,
            nodeResults,
            durationMs: Date.now() - runStart,
          };
        }

        const node = this._nodes.get(currentNodeId);

        // Should not happen after initial validation, but guard for dynamic routing
        if (!node) {
          throw new Error(
            `BlueprintRunner "${this._name}": node "${currentNodeId}" is not registered`,
          );
        }

        const nodeStart = Date.now();
        let result: StepResult;

        try {
          result = await this._executeWithTimeout(node, ctx);
        } catch (err) {
          const msg = err instanceof Error ? err.message : String(err);

          // T072: log the failure with context
          safeLogError(
            ctx.logger,
            `[${this._name}] Node "${node.id}" threw: ${msg}`,
          );

          nodeResults.push({
            nodeId: node.id,
            type: node.type,
            status: "error",
            duration: Date.now() - nodeStart,
            tokensUsed: 0,
          });

          // T072: route to error fallback (e.g. report) when available
          if (
            this._errorFallbackNodeId !== undefined &&
            !inErrorFallback &&
            node.id !== this._errorFallbackNodeId
          ) {
            inErrorFallback = true;
            fallbackError = `Node "${node.id}" threw: ${msg}`;
            currentNodeId = this._errorFallbackNodeId;
            continue;
          }

          return {
            status: "failed",
            error: `Node "${node.id}" threw: ${msg}`,
            nodeResults,
            durationMs: Date.now() - runStart,
          };
        }

        nodeResults.push({
          nodeId: node.id,
          type: node.type,
          status: result.status,
          duration: Date.now() - nodeStart,
          tokensUsed: result.tokensUsed ?? 0,
        });

        // "error" status from a node means unrecoverable failure
        if (result.status === "error") {
          // T072: log the failure with context
          safeLogError(
            ctx.logger,
            `[${this._name}] Node "${node.id}" returned error: ${result.error ?? "unknown"}`,
          );

          // T072: route to error fallback when available
          if (
            this._errorFallbackNodeId !== undefined &&
            !inErrorFallback &&
            node.id !== this._errorFallbackNodeId
          ) {
            inErrorFallback = true;
            fallbackError = result.error ?? `Node "${node.id}" returned status "error"`;
            currentNodeId = this._errorFallbackNodeId;
            continue;
          }

          return {
            status: "failed",
            error: result.error ?? `Node "${node.id}" returned status "error"`,
            nodeResults,
            durationMs: Date.now() - runStart,
          };
        }

        // Ask the node where to go next
        const nextId = node.next(result);

        if (nextId === null) {
          // Routing ended — run is complete
          break;
        }

        if (!this._nodes.has(nextId)) {
          throw new Error(
            `BlueprintRunner "${this._name}": node "${node.id}" routed to unknown node "${nextId}"`,
          );
        }

        currentNodeId = nextId;
      }

      return {
        status: fallbackError !== undefined ? "failed" : "succeeded",
        ...(fallbackError !== undefined ? { error: fallbackError } : {}),
        nodeResults,
        durationMs: Date.now() - runStart,
      };
    } finally {
      // Always clear the run timeout to avoid leaking timers (T073)
      if (runTimeoutId !== undefined) {
        clearTimeout(runTimeoutId);
      }
    }
  }

  /**
   * Execute a node wrapped in an optional per-node timeout race (T073).
   * If `_nodeTimeoutMs` is 0 the timeout is disabled.
   */
  private async _executeWithTimeout(
    node: BlueprintNode,
    ctx: RunContext,
  ): Promise<StepResult> {
    if (this._nodeTimeoutMs <= 0) {
      return node.execute(ctx);
    }

    const timeoutPromise = new Promise<never>((_, reject) => {
      const tid = setTimeout(
        () =>
          reject(
            new Error(`Node "${node.id}" timed out after ${this._nodeTimeoutMs}ms`),
          ),
        this._nodeTimeoutMs,
      );
      // Unref so the timer doesn't keep the process alive (T073)
      if (typeof tid === "object" && "unref" in tid) {
        (tid as { unref(): void }).unref();
      }
    });

    return Promise.race([node.execute(ctx), timeoutPromise]);
  }
}

