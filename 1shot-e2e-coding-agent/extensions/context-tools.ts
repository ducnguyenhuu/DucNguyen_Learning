/**
 * extensions/context-tools.ts — Context-tools Pi Extension (US2, T045)
 *
 * Registers four custom tools with the Pi SDK:
 *  - repo_map         : generate a compact symbol map of the workspace
 *  - semantic_search  : query the embedding index for relevant code chunks
 *  - symbol_nav       : find definitions and references for a symbol
 *  - dependency_graph : find importers / importees for a file
 *
 * Usage:
 *   const ext = createContextToolsExtension({ workspacePath, embeddingsIndexPath });
 *   // Pass to Pi SDK session:
 *   const sdkOptions = { ..., customTools: ext.toolDefinitions };
 */

import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "@mariozechner/pi-coding-agent";
import { generateRepoMap, formatRepoMap } from "../src/context/repo-map.js";
import { EmbeddingsIndex } from "../src/context/embeddings.js";
import { findDefinition, findReferences } from "../src/context/symbol-nav.js";
import { buildDepGraph, getImporters, getImportees } from "../src/context/dep-graph.js";

// ─── Types ────────────────────────────────────────────────────────────────────

export interface ContextToolsOptions {
  workspacePath: string;
  /** Absolute path to the vectra index directory. */
  embeddingsIndexPath: string;
  /** Embedding model name. Default: "Xenova/all-MiniLM-L6-v2" */
  embeddingModel?: string;
  /** Max tokens for repo map output. Default: 5_000 */
  repoMapMaxTokens?: number;
}

/** Shape returned by the factory function. */
export interface ContextToolsExtension {
  /** Extension name identifier. */
  name: string;
  /** Names of the registered tools (for documentation / inspection). */
  tools: string[];
  /**
   * Actual Pi SDK ToolDefinition objects.
   * Pass these to `customTools` in `CreateAgentSessionOptions` (T046).
   */
  toolDefinitions?: ToolDefinition[];
}

// ─── Private helpers ──────────────────────────────────────────────────────────

/**
 * Walk the workspace with generateRepoMap (which filters noise paths and
 * restricts to known source extensions) and return ollama rm glm4:9bworkspace-relative paths.
 *
 * We use a generous token budget so every file is included regardless of size.
 */
async function getAllSourceFiles(
  workspacePath: string,
): Promise<string[]> {
  const map = await generateRepoMap({ workspacePath, maxTokens: 999_999 });
  return map.files.map((f) => f.path);
}

/** Format a list of file paths with an optional header. */
function bulletList(header: string, paths: string[]): string {
  if (paths.length === 0) return `${header}\n  (none)`;
  return `${header}\n${paths.map((p) => `  ${p}`).join("\n")}`;
}

// ─── createContextToolsExtension ──────────────────────────────────────────────

/**
 * Factory function that creates and returns a context-tools Pi Extension.
 *
 * The returned `toolDefinitions` array can be passed to `customTools` in the
 * Pi SDK `CreateAgentSessionOptions` so the agent can call them during a run.
 *
 * All tools are synchronous to construct (no I/O at factory call time).
 * I/O happens only when the agent actually invokes a tool during execution.
 */
export function createContextToolsExtension(
  options: ContextToolsOptions,
): ContextToolsExtension {
  const {
    workspacePath,
    embeddingsIndexPath,
    embeddingModel,
    repoMapMaxTokens = 5_000,
  } = options;

  // Shared EmbeddingsIndex instance — lazily connects to vectra on first query.
  const embeddingsIndex = new EmbeddingsIndex({
    indexPath: embeddingsIndexPath,
    model: embeddingModel,
  });

  // ── Tool: repo_map ─────────────────────────────────────────────────────────

  const repoMapTool: ToolDefinition = {
    name: "repo_map",
    label: "Repository Map",
    description:
      "Generate a compact symbol map of the workspace showing files and their exported " +
      "functions, classes, interfaces, and types. Use this to orient yourself before " +
      "diving into specific files.",
    promptSnippet: "repo_map() → compact symbol map of the workspace",
    parameters: Type.Object({
      maxTokens: Type.Optional(
        Type.Number({
          description: `Maximum tokens for the output. Default: ${repoMapMaxTokens}.`,
          minimum: 100,
        }),
      ),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate, _ctx) {
      const { maxTokens } = params as { maxTokens?: number };
      const map = await generateRepoMap({
        workspacePath,
        maxTokens: maxTokens ?? repoMapMaxTokens,
      });
      const text = formatRepoMap(map);
      return {
        content: [{ type: "text" as const, text }],
        details: { fileCount: map.files.length, tokenCount: map.tokenCount },
      };
    },
  };

  // ── Tool: semantic_search ──────────────────────────────────────────────────

  const semanticSearchTool: ToolDefinition = {
    name: "semantic_search",
    label: "Semantic Search",
    description:
      "Search the embedding index for code chunks semantically similar to a natural-language " +
      "query. Returns the most relevant function/class bodies with file and line metadata. " +
      "Requires the index to have been built (run scripts/warm-cache.sh first).",
    promptSnippet: "semantic_search(query, topK?) → relevant code chunks",
    parameters: Type.Object({
      query: Type.String({
        description: "Natural-language description of the code you are looking for.",
      }),
      topK: Type.Optional(
        Type.Number({
          description: "Number of results to return. Default: 5.",
          minimum: 1,
          maximum: 20,
        }),
      ),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate, _ctx) {
      const { query, topK } = params as { query: string; topK?: number };
      const results = await embeddingsIndex.query(query, topK ?? 5);
      if (results.length === 0) {
        return {
          content: [{ type: "text" as const, text: "No results found. The embedding index may not be built yet." }],
          details: [],
        };
      }
      const text = results
        .map((r, i) =>
          `[${i + 1}] score=${r.score.toFixed(3)} ${r.chunk.filePath}:${r.chunk.startLine}-${r.chunk.endLine} ` +
          `[${r.chunk.kind}] ${r.chunk.name}\n${r.chunk.content}`,
        )
        .join("\n\n---\n\n");
      return {
        content: [{ type: "text" as const, text }],
        details: results,
      };
    },
  };

  // ── Tool: symbol_nav ──────────────────────────────────────────────────────

  const symbolNavTool: ToolDefinition = {
    name: "symbol_nav",
    label: "Symbol Navigation",
    description:
      "Find where a symbol (function, class, interface, variable) is defined, or list every " +
      "place it is referenced across the workspace. Useful for understanding impact of a change.",
    promptSnippet: "symbol_nav(symbol, operation, files?) → definitions or references",
    parameters: Type.Object({
      symbol: Type.String({
        description: "The exact symbol name to look up.",
      }),
      operation: Type.Union(
        [Type.Literal("definition"), Type.Literal("references")],
        { description: "'definition' to find declarations, 'references' to find all usages." },
      ),
      files: Type.Optional(
        Type.Array(Type.String(), {
          description:
            "Workspace-relative file paths to search. Defaults to all source files in the workspace.",
        }),
      ),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate, _ctx) {
      const { symbol, operation, files: paramFiles } = params as { symbol: string; operation: string; files?: string[] };
      const files = paramFiles ?? await getAllSourceFiles(workspacePath);
      const navOptions = { workspacePath };

      if (operation === "definition") {
        const defs = await findDefinition(symbol, files, navOptions);
        if (defs.length === 0) {
          return {
            content: [{ type: "text" as const, text: `No definition found for '${symbol}'.` }],
            details: [],
          };
        }
        const text = defs
          .map((d) =>
            `${d.filePath}:${d.line}:${d.column} [${d.kind}] ${d.name}` +
            (d.snippet ? `\n${d.snippet}` : ""),
          )
          .join("\n---\n");
        return { content: [{ type: "text" as const, text }], details: defs };
      }

      // "references"
      const refs = await findReferences(symbol, files, navOptions);
      if (refs.length === 0) {
        return {
          content: [{ type: "text" as const, text: `No references found for '${symbol}'.` }],
          details: [],
        };
      }
      const text = refs
        .map((r) =>
          `${r.filePath}:${r.line}:${r.column}` + (r.snippet ? `\n${r.snippet}` : ""),
        )
        .join("\n---\n");
      return { content: [{ type: "text" as const, text }], details: refs };
    },
  };

  // ── Tool: dependency_graph ─────────────────────────────────────────────────

  const dependencyGraphTool: ToolDefinition = {
    name: "dependency_graph",
    label: "Dependency Graph",
    description:
      "Trace the import graph for a file: find which files import it (importers) and which " +
      "files it imports (importees). Helps understand the blast radius of changes.",
    promptSnippet: "dependency_graph(filePath, direction?) → importers and/or importees",
    parameters: Type.Object({
      filePath: Type.String({
        description: "Workspace-relative path of the file to analyse (e.g. 'src/utils/run-command.ts').",
      }),
      direction: Type.Optional(
        Type.Union(
          [
            Type.Literal("importers"),
            Type.Literal("importees"),
            Type.Literal("both"),
          ],
          { description: "Which direction to trace. Default: 'both'." },
        ),
      ),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate, _ctx) {
      const { filePath, direction: paramDirection } = params as { filePath: string; direction?: string };
      const allFiles = await getAllSourceFiles(workspacePath);
      const graph = await buildDepGraph(allFiles, { workspacePath });
      const direction = paramDirection ?? "both";

      const sections: string[] = [];
      if (direction === "importers" || direction === "both") {
        const importers = getImporters(graph, filePath);
        sections.push(bulletList(`Importers of ${filePath}:`, importers));
      }
      if (direction === "importees" || direction === "both") {
        const importees = getImportees(graph, filePath);
        sections.push(bulletList(`Importees of ${filePath}:`, importees));
      }

      return {
        content: [{ type: "text" as const, text: sections.join("\n\n") }],
        details: { graph },
      };
    },
  };

  // ── Assemble extension ─────────────────────────────────────────────────────

  const toolDefinitions: ToolDefinition[] = [
    repoMapTool,
    semanticSearchTool,
    symbolNavTool,
    dependencyGraphTool,
  ];

  return {
    name: "context-tools",
    tools: toolDefinitions.map((t) => t.name),
    toolDefinitions,
  };
}
