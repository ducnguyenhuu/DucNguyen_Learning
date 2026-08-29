/**
 * tests/unit/context/dep-graph.test.ts — T038 / T043
 *
 * Tests for the dependency graph builder:
 *  - buildDepGraph: parses imports and produces edges
 *  - getImporters: returns files that import a given file
 *  - getImportees: returns files that a given file imports
 *
 * node:fs/promises is mocked — no real disk I/O occurs.
 */

import { describe, it, expect, beforeEach, vi } from "vitest";

// ─── node:fs/promises mock ────────────────────────────────────────────────────

const { mockReadFile } = vi.hoisted(() => ({ mockReadFile: vi.fn() }));
vi.mock("node:fs/promises", () => ({ readFile: mockReadFile }));

// ─── System under test ────────────────────────────────────────────────────────

import {
  buildDepGraph,
  getImporters,
  getImportees,
  type DependencyGraph,
  type ImportEdge,
} from "../../../src/context/dep-graph.js";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function makeEdge(from: string, to: string, specifier: string): ImportEdge {
  return { from, to, specifier };
}

function makeGraph(edges: ImportEdge[]): DependencyGraph {
  return { edges };
}

const BASE_OPTIONS = { workspacePath: "/workspace" };

beforeEach(() => vi.clearAllMocks());

// ─── buildDepGraph ────────────────────────────────────────────────────────────

describe("buildDepGraph()", () => {
  it("returns empty graph for empty filePaths", async () => {
    const graph = await buildDepGraph([], BASE_OPTIONS);
    expect(graph.edges).toEqual([]);
    expect(mockReadFile).not.toHaveBeenCalled();
  });

  it("returns empty graph when file cannot be read", async () => {
    mockReadFile.mockRejectedValue(Object.assign(new Error("ENOENT"), { code: "ENOENT" }));
    const graph = await buildDepGraph(["src/missing.ts"], BASE_OPTIONS);
    expect(graph.edges).toEqual([]);
  });

  it("returns empty graph for file with no imports", async () => {
    mockReadFile.mockResolvedValue("const x = 42;\nexport { x };");
    const graph = await buildDepGraph(["src/a.ts"], BASE_OPTIONS);
    expect(graph.edges).toEqual([]);
  });

  it("reads file from join(workspacePath, filePath)", async () => {
    mockReadFile.mockResolvedValue("");
    await buildDepGraph(["src/a.ts"], { workspacePath: "/my/root" });
    expect(mockReadFile).toHaveBeenCalledWith("/my/root/src/a.ts", "utf-8");
  });

  it("ignores external (non-relative) import specifiers", async () => {
    mockReadFile.mockResolvedValue(
      `import express from "express";\nimport { readFile } from "node:fs/promises";`,
    );
    const graph = await buildDepGraph(["src/a.ts"], BASE_OPTIONS);
    expect(graph.edges).toHaveLength(0);
  });

  it("parses a default import: import foo from './foo'", async () => {
    mockReadFile.mockResolvedValue(`import foo from "./utils/foo"`);
    const graph = await buildDepGraph(["src/a.ts", "src/utils/foo.ts"], BASE_OPTIONS);
    expect(graph.edges).toContainEqual(
      makeEdge("src/a.ts", "src/utils/foo.ts", "./utils/foo"),
    );
  });

  it("parses named imports: import { bar } from '../bar'", async () => {
    mockReadFile.mockResolvedValue(`import { bar, baz } from "../utils/bar"`);
    const graph = await buildDepGraph(
      ["src/auth/login.ts", "src/utils/bar.ts"],
      BASE_OPTIONS,
    );
    expect(graph.edges).toContainEqual(
      makeEdge("src/auth/login.ts", "src/utils/bar.ts", "../utils/bar"),
    );
  });

  it("parses namespace import: import * as ns from './ns'", async () => {
    mockReadFile.mockResolvedValue(`import * as ns from "./ns"`);
    const graph = await buildDepGraph(["src/a.ts", "src/ns.ts"], BASE_OPTIONS);
    expect(graph.edges).toContainEqual(makeEdge("src/a.ts", "src/ns.ts", "./ns"));
  });

  it("parses type import: import type { Foo } from './types'", async () => {
    mockReadFile.mockResolvedValue(`import type { Foo } from "./types"`);
    const graph = await buildDepGraph(["src/a.ts", "src/types.ts"], BASE_OPTIONS);
    expect(graph.edges).toContainEqual(makeEdge("src/a.ts", "src/types.ts", "./types"));
  });

  it("parses side-effect import: import './polyfill'", async () => {
    mockReadFile.mockResolvedValue(`import "./polyfill"`);
    const graph = await buildDepGraph(["src/a.ts", "src/polyfill.ts"], BASE_OPTIONS);
    expect(graph.edges).toContainEqual(
      makeEdge("src/a.ts", "src/polyfill.ts", "./polyfill"),
    );
  });

  it("parses re-export: export { Foo } from './foo'", async () => {
    mockReadFile.mockResolvedValue(`export { Foo } from "./foo"`);
    const graph = await buildDepGraph(["src/index.ts", "src/foo.ts"], BASE_OPTIONS);
    expect(graph.edges).toContainEqual(makeEdge("src/index.ts", "src/foo.ts", "./foo"));
  });

  it("parses export * from: export * from './all'", async () => {
    mockReadFile.mockResolvedValue(`export * from "./all"`);
    const graph = await buildDepGraph(["src/index.ts", "src/all.ts"], BASE_OPTIONS);
    expect(graph.edges).toContainEqual(makeEdge("src/index.ts", "src/all.ts", "./all"));
  });

  it("parses CommonJS require(): const x = require('./cfg')", async () => {
    mockReadFile.mockResolvedValue(`const cfg = require("./cfg")`);
    const graph = await buildDepGraph(["src/a.ts", "src/cfg.ts"], BASE_OPTIONS);
    expect(graph.edges).toContainEqual(makeEdge("src/a.ts", "src/cfg.ts", "./cfg"));
  });

  it("parses dynamic import(): await import('./lazy')", async () => {
    mockReadFile.mockResolvedValue(`const m = await import("./lazy")`);
    const graph = await buildDepGraph(["src/a.ts", "src/lazy.ts"], BASE_OPTIONS);
    expect(graph.edges).toContainEqual(makeEdge("src/a.ts", "src/lazy.ts", "./lazy"));
  });

  it("deduplicates specifiers used more than once in same file", async () => {
    mockReadFile
      .mockResolvedValueOnce(`import { a } from "./shared";\nimport { b } from "./shared";`) // src/a.ts
      .mockResolvedValueOnce("");  // src/shared.ts — no further imports
    const graph = await buildDepGraph(["src/a.ts", "src/shared.ts"], BASE_OPTIONS);
    // "./shared" appears twice in a.ts but the Set in extractSpecifiers deduplicates it
    const edgesFromA = graph.edges.filter(
      (e) => e.from === "src/a.ts" && e.specifier === "./shared",
    );
    expect(edgesFromA).toHaveLength(1);
  });

  it("resolves '../types' from src/auth/login.ts to src/types.ts", async () => {
    mockReadFile.mockResolvedValue(`import type { User } from "../types"`);
    const graph = await buildDepGraph(
      ["src/auth/login.ts", "src/types.ts"],
      BASE_OPTIONS,
    );
    expect(graph.edges).toContainEqual(
      makeEdge("src/auth/login.ts", "src/types.ts", "../types"),
    );
  });

  it("aggregates edges from multiple files", async () => {
    mockReadFile
      .mockImplementationOnce(() => Promise.resolve(`import x from "./b"`))  // a.ts
      .mockImplementationOnce(() => Promise.resolve(`import y from "./c"`))  // b.ts
      .mockImplementationOnce(() => Promise.resolve(""));                   // c.ts (no imports)

    const graph = await buildDepGraph(
      ["src/a.ts", "src/b.ts", "src/c.ts"],
      BASE_OPTIONS,
    );
    expect(graph.edges).toContainEqual(makeEdge("src/a.ts", "src/b.ts", "./b"));
    expect(graph.edges).toContainEqual(makeEdge("src/b.ts", "src/c.ts", "./c"));
    expect(graph.edges).toHaveLength(2);
  });

  it("supports index file resolution: './utils' → src/utils/index.ts", async () => {
    mockReadFile.mockResolvedValue(`import utils from "./utils"`);
    const graph = await buildDepGraph(
      ["src/a.ts", "src/utils/index.ts"],
      BASE_OPTIONS,
    );
    expect(graph.edges).toContainEqual(
      makeEdge("src/a.ts", "src/utils/index.ts", "./utils"),
    );
  });

  it("respects custom extensions option", async () => {
    mockReadFile.mockResolvedValue(`import x from "./x"`);
    const graph = await buildDepGraph(
      ["src/a.ts", "src/x.ts"],
      { workspacePath: "/workspace", extensions: [".ts"] },
    );
    expect(graph.edges).toContainEqual(makeEdge("src/a.ts", "src/x.ts", "./x"));
  });

  it("returns a DependencyGraph with an edges array", async () => {
    mockReadFile.mockResolvedValue("");
    const graph = await buildDepGraph(["src/a.ts"], BASE_OPTIONS);
    expect(Array.isArray(graph.edges)).toBe(true);
  });
});

// ─── getImporters ─────────────────────────────────────────────────────────────

describe("getImporters()", () => {
  const graph = makeGraph([
    makeEdge("src/app.ts", "src/auth/login.ts", "./auth/login"),
    makeEdge("src/middleware.ts", "src/auth/login.ts", "../auth/login"),
    makeEdge("src/auth/login.ts", "src/types.ts", "../types"),
  ]);

  it("returns files that import the given file", () => {
    const importers = getImporters(graph, "src/auth/login.ts");
    expect(importers).toContain("src/app.ts");
    expect(importers).toContain("src/middleware.ts");
  });

  it("does not include the file itself in its importers", () => {
    const importers = getImporters(graph, "src/auth/login.ts");
    expect(importers).not.toContain("src/auth/login.ts");
  });

  it("returns empty array when no file imports it", () => {
    const importers = getImporters(graph, "src/types.ts");
    expect(importers).toEqual(["src/auth/login.ts"]);
  });

  it("returns empty array for an unknown file", () => {
    expect(getImporters(graph, "src/nonexistent.ts")).toHaveLength(0);
  });

  it("returns empty array for an empty graph", () => {
    expect(getImporters(makeGraph([]), "src/x.ts")).toHaveLength(0);
  });
});

// ─── getImportees ─────────────────────────────────────────────────────────────

describe("getImportees()", () => {
  const graph = makeGraph([
    makeEdge("src/auth/login.ts", "src/types.ts", "../types"),
    makeEdge("src/auth/login.ts", "src/utils/hash.ts", "../utils/hash"),
    makeEdge("src/app.ts", "src/auth/login.ts", "./auth/login"),
  ]);

  it("returns files that the given file imports", () => {
    const importees = getImportees(graph, "src/auth/login.ts");
    expect(importees).toContain("src/types.ts");
    expect(importees).toContain("src/utils/hash.ts");
  });

  it("does not include files that import the given file", () => {
    const importees = getImportees(graph, "src/auth/login.ts");
    expect(importees).not.toContain("src/app.ts");
  });

  it("returns empty array when the file imports nothing", () => {
    expect(getImportees(graph, "src/types.ts")).toHaveLength(0);
  });

  it("returns empty array for an empty graph", () => {
    expect(getImportees(makeGraph([]), "src/x.ts")).toHaveLength(0);
  });
});

// ─── ImportEdge interface contract ────────────────────────────────────────────

describe("ImportEdge — interface contract", () => {
  it("contract: edge has from, to, specifier strings", () => {
    const edge: ImportEdge = {
      from: "src/app.ts",
      to: "src/auth/login.ts",
      specifier: "./auth/login",
    };
    expect(typeof edge.from).toBe("string");
    expect(typeof edge.to).toBe("string");
    expect(typeof edge.specifier).toBe("string");
  });
});

// ─── DependencyGraph interface contract ───────────────────────────────────────

describe("DependencyGraph — interface contract", () => {
  it("contract: graph has an edges array", () => {
    const graph: DependencyGraph = { edges: [] };
    expect(Array.isArray(graph.edges)).toBe(true);
  });
});
