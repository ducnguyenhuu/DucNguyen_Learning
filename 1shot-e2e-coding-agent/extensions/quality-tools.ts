/**
 * extensions/quality-tools.ts — Quality-tools Pi Extension (US3, T050)
 *
 * Registers two custom tools with the Pi SDK:
 *  - run_test : execute the project's test command and return structured PASSED/FAILED output
 *  - run_lint : execute the project's lint command and return structured PASSED/FAILED output
 *
 * Both tools run the command in the workspace directory and return a structured
 * result so the fix-failures agent can parse test/lint output without shell gymnastics.
 *
 * Usage:
 *   const ext = createQualityToolsExtension({ workspacePath, testCommand, lintCommand });
 *   // Pass to Pi SDK session:
 *   const sdkOptions = { ..., customTools: ext.toolDefinitions };
 */

import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "@mariozechner/pi-coding-agent";
import { runCommand } from "../src/utils/run-command.js";

// ─── Types ────────────────────────────────────────────────────────────────────

export interface QualityToolsOptions {
  /** Absolute path to the workspace root where commands will be executed. */
  workspacePath: string;
  /** Shell command to run tests (e.g. "npm test", "vitest run"). */
  testCommand: string;
  /** Shell command to run linter (e.g. "npm run lint", "eslint ."). */
  lintCommand: string;
}

/** Shape returned by the factory function. */
export interface QualityToolsExtension {
  /** Extension name identifier. */
  name: string;
  /** Names of the registered tools (for documentation / inspection). */
  tools: string[];
  /**
   * Actual Pi SDK ToolDefinition objects.
   * Pass these to `customTools` in `CreateAgentSessionOptions` (T052).
   */
  toolDefinitions: ToolDefinition[];
}

// ─── Private helpers ──────────────────────────────────────────────────────────

/**
 * Format a command result into structured PASSED/FAILED output.
 * The structured format lets the fix-failures agent reliably detect success/failure
 * without parsing exit codes.
 */
function formatResult(
  label: string,
  command: string,
  exitCode: number,
  stdout: string,
  stderr: string,
): string {
  const status = exitCode === 0 ? "PASSED" : "FAILED";
  const output = [stdout, stderr].filter(Boolean).join("\n");
  return [
    `${label}: ${status}`,
    `Command: ${command}`,
    `Exit code: ${exitCode}`,
    output ? `\nOutput:\n${output}` : "(no output)",
  ].join("\n");
}

// ─── createQualityToolsExtension ─────────────────────────────────────────────

/**
 * Factory function that creates and returns a quality-tools Pi Extension.
 *
 * The returned `toolDefinitions` array can be passed to `customTools` in the
 * Pi SDK `CreateAgentSessionOptions` so the fix-failures agent can call them
 * during a retry session.
 *
 * All tools are synchronous to construct (no I/O at factory call time).
 * I/O happens only when the agent actually invokes a tool during execution.
 */
export function createQualityToolsExtension(
  options: QualityToolsOptions,
): QualityToolsExtension {
  const { workspacePath, testCommand, lintCommand } = options;

  // ── Tool: run_test ─────────────────────────────────────────────────────────

  const runTestTool: ToolDefinition = {
    name: "run_test",
    label: "Run Tests",
    description:
      "Execute the project's test suite and return structured PASSED/FAILED output. " +
      "Use this after making code changes to verify whether tests pass. " +
      "The output includes the full test runner stdout/stderr so you can diagnose failures.",
    promptSnippet: "run_test() → PASSED or FAILED with full test output",
    parameters: Type.Object({}),
    async execute(_toolCallId, _params, _signal, _onUpdate, _ctx) {
      const { stdout, stderr, exitCode } = await runCommand(testCommand, workspacePath);
      const text = formatResult("TEST", testCommand, exitCode, stdout, stderr);
      return {
        content: [{ type: "text" as const, text }],
        details: { exitCode, stdout, stderr },
      };
    },
  };

  // ── Tool: run_lint ─────────────────────────────────────────────────────────

  const runLintTool: ToolDefinition = {
    name: "run_lint",
    label: "Run Linter",
    description:
      "Execute the project's lint command and return structured PASSED/FAILED output. " +
      "Use this after making code changes to verify there are no lint errors. " +
      "The output includes the full linter stdout/stderr so you can diagnose violations.",
    promptSnippet: "run_lint() → PASSED or FAILED with full lint output",
    parameters: Type.Object({}),
    async execute(_toolCallId, _params, _signal, _onUpdate, _ctx) {
      const { stdout, stderr, exitCode } = await runCommand(lintCommand, workspacePath);
      const text = formatResult("LINT", lintCommand, exitCode, stdout, stderr);
      return {
        content: [{ type: "text" as const, text }],
        details: { exitCode, stdout, stderr },
      };
    },
  };

  // ── Assemble extension ─────────────────────────────────────────────────────

  const toolDefinitions: ToolDefinition[] = [runTestTool, runLintTool];

  return {
    name: "quality-tools",
    tools: toolDefinitions.map((t) => t.name),
    toolDefinitions,
  };
}
