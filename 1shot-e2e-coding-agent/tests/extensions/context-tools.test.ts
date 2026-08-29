/**
 * tests/extensions/context-tools.test.ts — T039
 *
 * Integration tests for the context-tools Pi Extension factory (T045).
 * Verifies registration shape, options validation, and expected tool list.
 */

import { describe, it, expect } from "vitest";

import {
  createContextToolsExtension,
  type ContextToolsOptions,
  type ContextToolsExtension,
} from "../../extensions/context-tools.js";

// ─── Helpers ──────────────────────────────────────────────────────────────────

const BASE_OPTIONS: ContextToolsOptions = {
  workspacePath: "/workspace/test-repo",
  embeddingsIndexPath: "/workspace/.index",
  embeddingModel: "Xenova/all-MiniLM-L6-v2",
  repoMapMaxTokens: 5_000,
};

// ─── createContextToolsExtension ──────────────────────────────────────────────

describe("createContextToolsExtension()", () => {
  // ── Factory behaviour (T045 implemented) ───────────────────────────────────

  it("returns a ContextToolsExtension without throwing", () => {
    expect(() => createContextToolsExtension(BASE_OPTIONS)).not.toThrow();
  });

  it("is a synchronous factory function", () => {
    const result = createContextToolsExtension(BASE_OPTIONS);
    // Must be a plain object (not a Promise) — synchronous construction
    expect(result).toBeDefined();
    expect(typeof (result as unknown as { then?: unknown }).then).not.toBe("function");
  });

  // ── ContextToolsOptions — interface contract ────────────────────────────────

  it("contract: options require workspacePath", () => {
    const opts: ContextToolsOptions = {
      workspacePath: "/workspace",
      embeddingsIndexPath: "/workspace/.index",
    };
    expect(typeof opts.workspacePath).toBe("string");
  });

  it("contract: options require embeddingsIndexPath", () => {
    const opts: ContextToolsOptions = {
      workspacePath: "/workspace",
      embeddingsIndexPath: "/data/index",
    };
    expect(typeof opts.embeddingsIndexPath).toBe("string");
  });

  it("contract: embeddingModel is optional", () => {
    const opts: ContextToolsOptions = {
      workspacePath: "/workspace",
      embeddingsIndexPath: "/data/index",
    };
    expect(opts.embeddingModel).toBeUndefined();
  });

  it("contract: repoMapMaxTokens is optional", () => {
    const opts: ContextToolsOptions = {
      workspacePath: "/workspace",
      embeddingsIndexPath: "/data/index",
    };
    expect(opts.repoMapMaxTokens).toBeUndefined();
  });
});

// ─── ContextToolsExtension — factory output ───────────────────────────────────

describe("ContextToolsExtension — factory output (T045)", () => {
  it("returns name 'context-tools'", () => {
    const ext = createContextToolsExtension(BASE_OPTIONS);
    expect(ext.name).toBe("context-tools");
  });

  it("returns a tools string array", () => {
    const ext = createContextToolsExtension(BASE_OPTIONS);
    expect(Array.isArray(ext.tools)).toBe(true);
  });

  it("registers the four expected tools", () => {
    const ext = createContextToolsExtension(BASE_OPTIONS);
    expect(ext.tools).toContain("repo_map");
    expect(ext.tools).toContain("semantic_search");
    expect(ext.tools).toContain("symbol_nav");
    expect(ext.tools).toContain("dependency_graph");
  });

  it("registers exactly four tools", () => {
    const ext = createContextToolsExtension(BASE_OPTIONS);
    expect(ext.tools).toHaveLength(4);
  });

  it("tool names are strings", () => {
    const ext = createContextToolsExtension(BASE_OPTIONS);
    for (const tool of ext.tools) {
      expect(typeof tool).toBe("string");
    }
  });

  it("exposes toolDefinitions array", () => {
    const ext = createContextToolsExtension(BASE_OPTIONS);
    expect(Array.isArray(ext.toolDefinitions)).toBe(true);
  });

  it("toolDefinitions length matches tools length", () => {
    const ext = createContextToolsExtension(BASE_OPTIONS);
    expect(ext.toolDefinitions).toHaveLength(ext.tools.length);
  });

  it("each toolDefinition has name, label, description, parameters, execute", () => {
    const ext = createContextToolsExtension(BASE_OPTIONS);
    for (const def of ext.toolDefinitions ?? []) {
      expect(typeof def.name).toBe("string");
      expect(typeof def.label).toBe("string");
      expect(typeof def.description).toBe("string");
      expect(def.parameters).toBeDefined();
      expect(typeof def.execute).toBe("function");
    }
  });

  it("toolDefinition names match tools list", () => {
    const ext = createContextToolsExtension(BASE_OPTIONS);
    const defNames = (ext.toolDefinitions ?? []).map((d) => d.name);
    expect(defNames).toEqual(ext.tools);
  });
});

// ─── ContextToolsExtension — interface contract ───────────────────────────────

describe("ContextToolsExtension — interface shape", () => {
  it("interface accepts {name, tools} without toolDefinitions (optional field)", () => {
    // Construct a conforming object — toolDefinitions is optional
    const ext: ContextToolsExtension = {
      name: "context-tools",
      tools: ["repo_map", "semantic_search", "symbol_nav", "dependency_graph"],
    };
    expect(typeof ext.name).toBe("string");
    expect(Array.isArray(ext.tools)).toBe(true);
  });
});

// ─── Tool-level parameter contracts ──────────────────────────────────────────

describe("tool parameter contracts (T045)", () => {
  it("repo_map toolDefinition has optional maxTokens parameter", () => {
    const ext = createContextToolsExtension(BASE_OPTIONS);
    const def = (ext.toolDefinitions ?? []).find((d) => d.name === "repo_map");
    expect(def).toBeDefined();
    const props = def!.parameters.properties as Record<string, unknown>;
    expect(props).toHaveProperty("maxTokens");
  });

  it("semantic_search toolDefinition has required query parameter", () => {
    const ext = createContextToolsExtension(BASE_OPTIONS);
    const def = (ext.toolDefinitions ?? []).find((d) => d.name === "semantic_search");
    expect(def).toBeDefined();
    const props = def!.parameters.properties as Record<string, unknown>;
    expect(props).toHaveProperty("query");
    expect(props).toHaveProperty("topK");
  });

  it("symbol_nav toolDefinition has symbol, operation, and optional files parameters", () => {
    const ext = createContextToolsExtension(BASE_OPTIONS);
    const def = (ext.toolDefinitions ?? []).find((d) => d.name === "symbol_nav");
    expect(def).toBeDefined();
    const props = def!.parameters.properties as Record<string, unknown>;
    expect(props).toHaveProperty("symbol");
    expect(props).toHaveProperty("operation");
    expect(props).toHaveProperty("files");
  });

  it("dependency_graph toolDefinition has filePath and optional direction parameters", () => {
    const ext = createContextToolsExtension(BASE_OPTIONS);
    const def = (ext.toolDefinitions ?? []).find((d) => d.name === "dependency_graph");
    expect(def).toBeDefined();
    const props = def!.parameters.properties as Record<string, unknown>;
    expect(props).toHaveProperty("filePath");
    expect(props).toHaveProperty("direction");
  });
});
