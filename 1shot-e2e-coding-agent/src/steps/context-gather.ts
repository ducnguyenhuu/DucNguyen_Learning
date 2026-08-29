/**
 * src/steps/context-gather.ts — Context Gather step (FR-003, FR-017, T046)
 *
 * Second node in the standard blueprint. Responsible for:
 *  1. Creating a read-only Pi session (read/grep/find/ls tools only)
 *  2. Loading the context-tools extension (repo_map, semantic_search, symbol_nav, dependency_graph)
 *  3. Prompting the LLM to explore the workspace using multi-signal retrieval
 *  4. Parsing the response for relevant file paths and an understanding summary
 *  5. Mutating ctx.relevantFiles and ctx.understanding for downstream nodes
 *
 * Returns a StepResult with:
 *  - data.relevantFiles  — list of file paths identified as relevant
 *  - data.understanding  — full LLM response (structured understanding)
 *  - tokensUsed          — cumulative tokens consumed in this session
 */

import { fileURLToPath } from "node:url";
import { dirname, join, resolve } from "node:path";
import { readFile } from "node:fs/promises";
import {
  createSession,
  runPrompt,
  getTokensUsed,
} from "../adapters/pi-sdk.js";
import { createContextToolsExtension } from "../../extensions/context-tools.js";
import type { RunContext, StepResult } from "../types.js";

// ─── Embedded system prompt ───────────────────────────────────────────────────

/**
 * Default system prompt for the context-gather node.
 * Instructs the agent to use all available tools for multi-signal retrieval.
 */
const DEFAULT_SYSTEM_PROMPT = `You are a code analysis agent. Your job is to explore a repository
and identify which files are relevant to a given coding task.

Use all available tools for multi-signal context gathering:
  - repo_map        : Start here — get a compact symbol overview of the entire workspace
  - semantic_search : Find code chunks semantically similar to the task description
  - symbol_nav      : Locate definitions and references for specific named symbols
  - dependency_graph: Trace import relationships (importers/importees) for a file
  - read, grep, find, ls: Precise keyword search and targeted file exploration

Combine signals — semantic similarity, keyword search, and dependency tracing — for thorough coverage.

When done, output:
1. A list of relevant file paths (one per line, prefixed with "- ")
2. A brief understanding of the codebase structure and how it relates to the task

Do not modify any files.`.trim();

// ─── Skill loader ───────────────────────────────────────────────────────────────

/**
 * Load skill instructions from the corresponding SKILL.md.
 * Falls back to DEFAULT_SYSTEM_PROMPT if the file is absent.
 */
async function loadSkill(skillDir: string): Promise<string> {
  const skillPath = resolve(dirname(fileURLToPath(import.meta.url)), "../../skills", skillDir, "SKILL.md");
  try {
    return (await readFile(skillPath, "utf-8")).trim();
  } catch {
    return DEFAULT_SYSTEM_PROMPT;
  }
}

// ─── File path parser ─────────────────────────────────────────────────────────

/**
 * Extract relative file paths from the LLM's text response.
 * Matches lines of the form:
 *   - src/auth/login.ts
 *   * src/auth/user.ts
 *   src/auth/user.ts
 */
const FILE_PATH_REGEX = /^[-*\s]*((?:[\w.-]+\/)+[\w.-]+\.[a-z]{1,10})\s*$/;

function parseRelevantFiles(output: string): string[] {
  const files: string[] = [];
  for (const line of output.split("\n")) {
    const match = line.match(FILE_PATH_REGEX);
    if (match?.[1]) {
      files.push(match[1]);
    }
  }
  return files;
}

// ─── contextGatherStep ────────────────────────────────────────────────────────

export async function contextGatherStep(ctx: RunContext): Promise<StepResult> {
  // ── 0. Load skill instructions ─────────────────────────────────────────────
  const systemPrompt = await loadSkill("explore-codebase");

  // ── 1. Load AGENTS.md (non-fatal if absent) ────────────────────────────────
  let agentsMd = "";
  try {
    agentsMd = await readFile(join(ctx.workspacePath, "AGENTS.md"), "utf-8");
  } catch {
    // File absent or unreadable — proceed without it
  }

  // ── 2. Build user prompt ───────────────────────────────────────────────────
  const agentsMdSection = agentsMd
    ? `\n\n## Project Rules (AGENTS.md)\n${agentsMd}`
    : "";

  const userPrompt =
    `## Task\n${ctx.task.description}\n\n` +
    `## Workspace\n${ctx.workspacePath}${agentsMdSection}\n\n` +
    `Explore the workspace and identify the files most relevant to this task. ` +
    `List each relevant file path on its own line prefixed with "- ".`;

  // ── 3. Resolve model from config ───────────────────────────────────────────
  const provider = ctx.config.provider.default;
  const model =
    provider === "anthropic"
      ? (ctx.config.provider.anthropicModel ?? "claude-sonnet-4-20250514")
      : (ctx.config.provider.openaiModel ?? "gpt-4.1");

  // ── 4. Build context-tools extension (multi-signal retrieval) ─────────────
  const embeddingsIndexPath =
    ctx.config.extensions?.contextTools ?? join(ctx.workspacePath, ".index");
  const contextToolsExt = createContextToolsExtension({
    workspacePath: ctx.workspacePath,
    embeddingsIndexPath,
    embeddingModel: ctx.config.context?.embeddingModel,
    repoMapMaxTokens: ctx.config.context?.repoMapMaxTokens,
  });

  // ── 5. Create Pi session with read-only + context tools ────────────────────
  let handle;
  try {
    handle = await createSession(
      {
        systemPrompt,
        tools: ["read", "grep", "find", "ls"],
        extensions: [],
        provider,
        model,
        customTools: contextToolsExt.toolDefinitions,
      },
      { cwd: ctx.workspacePath },
    );
  } catch (err) {
    return {
      status: "error",
      error: err instanceof Error ? err.message : String(err),
    };
  }

  // ── 6. Run prompt ──────────────────────────────────────────────────────────
  let output: string;
  try {
    output = await runPrompt(handle, userPrompt);
  } catch (err) {
    return {
      status: "error",
      error: err instanceof Error ? err.message : String(err),
    };
  }

  // ── 7. Parse output ────────────────────────────────────────────────────────
  const relevantFiles = parseRelevantFiles(output);
  const understanding = output;

  // ── 8. Update ctx ──────────────────────────────────────────────────────────
  ctx.relevantFiles = relevantFiles;
  ctx.understanding = understanding;

  // ── 9. Record token usage ──────────────────────────────────────────────────
  const tokensUsed = getTokensUsed(handle);

  return {
    status: "passed",
    tokensUsed,
    data: {
      relevantFiles,
      understanding,
    },
  };
}
