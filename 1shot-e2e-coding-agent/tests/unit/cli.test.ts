/**
 * tests/unit/cli.test.ts — T016
 *
 * Tests CLI `run` command argument parsing and option handling.
 * The runner itself is mocked — we only verify what the CLI parses and passes.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";

// Hoist mock before any CLI import (vitest hoists vi.mock automatically)
vi.mock("../../src/runner.js", () => ({
  runAgent: vi.fn().mockResolvedValue({ status: "succeeded" }),
}));

import { createProgram } from "../../src/cli.js";
import { runAgent } from "../../src/runner.js";

const mockRunAgent = vi.mocked(runAgent);

function parse(args: string[]) {
  // createProgram() calls .exitOverride() so Commander throws instead of process.exit
  return createProgram().parseAsync(["node", "duc-e2e-agent", ...args]);
}

describe("CLI run command", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // ─── Required argument ────────────────────────────────────────────────────

  it("requires a task description argument", async () => {
    await expect(parse(["run"])).rejects.toThrow();
  });

  it("accepts a quoted task description", async () => {
    await parse(["run", "Fix the login bug"]);
    expect(mockRunAgent).toHaveBeenCalledOnce();
    const [task] = mockRunAgent.mock.calls[0]!;
    expect(task).toBe("Fix the login bug");
  });

  // ─── Default option values ────────────────────────────────────────────────

  it("uses ./pi-agent.config.ts as default config path", async () => {
    await parse(["run", "fix bug"]);
    const [, opts] = mockRunAgent.mock.calls[0]!;
    expect(opts.config).toBe("./pi-agent.config.ts");
  });

  it("defaults dry-run to false", async () => {
    await parse(["run", "fix bug"]);
    const [, opts] = mockRunAgent.mock.calls[0]!;
    expect(opts.dryRun).toBe(false);
  });

  it("defaults verbose to false", async () => {
    await parse(["run", "fix bug"]);
    const [, opts] = mockRunAgent.mock.calls[0]!;
    expect(opts.verbose).toBe(false);
  });

  it("defaults output-dir to ./runs/", async () => {
    await parse(["run", "fix bug"]);
    const [, opts] = mockRunAgent.mock.calls[0]!;
    expect(opts.outputDir).toBe("./runs/");
  });

  it("defaults provider and model to undefined (resolved from config)", async () => {
    await parse(["run", "fix bug"]);
    const [, opts] = mockRunAgent.mock.calls[0]!;
    expect(opts.provider).toBeUndefined();
    expect(opts.model).toBeUndefined();
  });

  // ─── Option parsing ───────────────────────────────────────────────────────

  it("parses --config / -c", async () => {
    await parse(["run", "fix bug", "--config", "./custom.config.ts"]);
    const [, opts] = mockRunAgent.mock.calls[0]!;
    expect(opts.config).toBe("./custom.config.ts");
  });

  it("parses -c short form", async () => {
    await parse(["run", "fix bug", "-c", "./my.config.ts"]);
    const [, opts] = mockRunAgent.mock.calls[0]!;
    expect(opts.config).toBe("./my.config.ts");
  });

  it("parses --provider / -p", async () => {
    await parse(["run", "fix bug", "--provider", "openai"]);
    const [, opts] = mockRunAgent.mock.calls[0]!;
    expect(opts.provider).toBe("openai");
  });

  it("parses --model / -m", async () => {
    await parse(["run", "fix bug", "--model", "gpt-4.1"]);
    const [, opts] = mockRunAgent.mock.calls[0]!;
    expect(opts.model).toBe("gpt-4.1");
  });

  it("parses --dry-run flag", async () => {
    await parse(["run", "fix bug", "--dry-run"]);
    const [, opts] = mockRunAgent.mock.calls[0]!;
    expect(opts.dryRun).toBe(true);
  });

  it("parses --max-retries as a number", async () => {
    await parse(["run", "fix bug", "--max-retries", "3"]);
    const [, opts] = mockRunAgent.mock.calls[0]!;
    expect(opts.maxRetries).toBe(3);
  });

  it("parses --max-tokens as a number", async () => {
    await parse(["run", "fix bug", "--max-tokens", "50000"]);
    const [, opts] = mockRunAgent.mock.calls[0]!;
    expect(opts.maxTokens).toBe(50_000);
  });

  it("parses --timeout as a number", async () => {
    await parse(["run", "fix bug", "--timeout", "120"]);
    const [, opts] = mockRunAgent.mock.calls[0]!;
    expect(opts.timeout).toBe(120);
  });

  it("parses --verbose / -v", async () => {
    await parse(["run", "fix bug", "--verbose"]);
    const [, opts] = mockRunAgent.mock.calls[0]!;
    expect(opts.verbose).toBe(true);
  });

  it("parses -v short form", async () => {
    await parse(["run", "fix bug", "-v"]);
    const [, opts] = mockRunAgent.mock.calls[0]!;
    expect(opts.verbose).toBe(true);
  });

  it("parses --output-dir", async () => {
    await parse(["run", "fix bug", "--output-dir", "/tmp/runs"]);
    const [, opts] = mockRunAgent.mock.calls[0]!;
    expect(opts.outputDir).toBe("/tmp/runs");
  });

  it("parses multiple options together", async () => {
    await parse([
      "run", "fix bug",
      "--provider", "anthropic",
      "--model", "claude-sonnet-4-20250514",
      "--verbose",
      "--dry-run",
      "--max-retries", "1",
    ]);
    const [task, opts] = mockRunAgent.mock.calls[0]!;
    expect(task).toBe("fix bug");
    expect(opts.provider).toBe("anthropic");
    expect(opts.model).toBe("claude-sonnet-4-20250514");
    expect(opts.verbose).toBe(true);
    expect(opts.dryRun).toBe(true);
    expect(opts.maxRetries).toBe(1);
  });

  // ─── Runner invocation ────────────────────────────────────────────────────

  it("calls runAgent exactly once per parse", async () => {
    await parse(["run", "fix bug"]);
    expect(mockRunAgent).toHaveBeenCalledOnce();
  });

  it("passes task description as first argument to runAgent", async () => {
    await parse(["run", "Add email validation to user endpoint"]);
    expect(mockRunAgent.mock.calls[0]![0]).toBe("Add email validation to user endpoint");
  });
});
