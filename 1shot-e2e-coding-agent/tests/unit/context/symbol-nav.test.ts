/**
 * tests/unit/context/symbol-nav.test.ts — T083 / T042
 *
 * Tests for the symbol navigation module (full implementation after T042).
 *  - findDefinition: locate where a symbol is defined
 *  - findReferences: find all usages of a symbol
 *
 * Both web-tree-sitter and node:fs/promises are fully mocked so no WASM or
 * disk I/O occurs during the test run.
 */

import { describe, it, expect, beforeEach, vi } from "vitest";

// ─── web-tree-sitter mock ─────────────────────────────────────────────────────

const { mockInit, mockLoad, mockParse, mockSetLanguage } = vi.hoisted(() => ({
  mockInit: vi.fn().mockResolvedValue(undefined),
  mockLoad: vi.fn().mockResolvedValue({}),
  mockParse: vi.fn(),
  mockSetLanguage: vi.fn(),
}));

vi.mock("web-tree-sitter", () => {
  const MockParser = vi.fn().mockImplementation(() => ({
    parse: mockParse,
    setLanguage: mockSetLanguage,
  }));
  (MockParser as unknown as Record<string, unknown>).init = mockInit;
  (MockParser as unknown as Record<string, unknown>).Language = { load: mockLoad };
  return { default: MockParser };
});

// ─── node:fs/promises mock ────────────────────────────────────────────────────

const { mockReadFile } = vi.hoisted(() => ({
  mockReadFile: vi.fn(),
}));

vi.mock("node:fs/promises", () => ({ readFile: mockReadFile }));

// ─── node:module mock (require.resolve for WASM paths) ───────────────────────

vi.mock("node:module", () => ({
  createRequire: () => ({ resolve: (p: string) => p }),
}));

// ─── System under test ────────────────────────────────────────────────────────

import {
  findDefinition,
  findReferences,
  type SymbolDefinition,
  type SymbolLocation,
} from "../../../src/context/symbol-nav.js";

// ─── Node factory helpers ─────────────────────────────────────────────────────

type FakePosition = { row: number; column: number };

interface FakeNode {
  type: string;
  text: string;
  startPosition: FakePosition;
  endPosition: FakePosition;
  children: FakeNode[];
  namedChildren: FakeNode[];
  childForFieldName: (name: string) => FakeNode | null;
}

function makeNode(
  type: string,
  startRow: number,
  endRow: number,
  fields: Record<string, FakeNode | null> = {},
  children: FakeNode[] = [],
  text = "",
): FakeNode {
  return {
    type,
    text,
    startPosition: { row: startRow, column: 0 },
    endPosition: { row: endRow, column: 0 },
    children,
    namedChildren: children.filter((c) => c.type !== "comment"),
    childForFieldName: (name: string) => fields[name] ?? null,
  };
}

function nameNode(text: string): FakeNode {
  return makeNode("identifier", 0, 0, {}, [], text);
}

/** Build a root node wrapping the given top-level children. */
function rootWith(...children: FakeNode[]): FakeNode {
  return makeNode("program", 0, 100, {}, children);
}

/** Fake tree returned by mockParse */
function fakeTree(root: FakeNode) {
  return { rootNode: root };
}

const SOURCE_LINES = [
  "// line 0",
  "// line 1",
  "export function validateCredentials(u: string) {",  // row 2
  "  return true;",
  "}",
  "// line 5",
  "// line 6",
];
const SOURCE = SOURCE_LINES.join("\n");

const opts = { workspacePath: "/workspace" };

beforeEach(() => {
  vi.clearAllMocks();
  mockReadFile.mockResolvedValue(SOURCE);
  mockParse.mockReturnValue(fakeTree(rootWith())); // default: empty AST
});

// ─── findDefinition ───────────────────────────────────────────────────────────

describe("findDefinition()", () => {
  it("returns empty array for empty filePaths list", async () => {
    const result = await findDefinition("foo", [], opts);
    expect(result).toEqual([]);
    expect(mockReadFile).not.toHaveBeenCalled();
  });

  it("returns empty array when file cannot be read (I/O error)", async () => {
    mockReadFile.mockRejectedValue(Object.assign(new Error("ENOENT"), { code: "ENOENT" }));
    const result = await findDefinition("foo", ["src/missing.ts"], opts);
    expect(result).toEqual([]);
  });

  it("returns empty array for unsupported file extension", async () => {
    mockReadFile.mockResolvedValue("content");
    const result = await findDefinition("foo", ["src/file.unknown"], opts);
    expect(result).toEqual([]);
    expect(mockParse).not.toHaveBeenCalled();
  });

  it("returns empty array when symbol is not found in file", async () => {
    const funcDecl = makeNode(
      "function_declaration", 2, 4,
      { name: nameNode("otherFunction") },
    );
    mockParse.mockReturnValue(fakeTree(rootWith(funcDecl)));

    const result = await findDefinition("validateCredentials", ["src/auth.ts"], opts);
    expect(result).toEqual([]);
  });

  it("finds a function_declaration by name", async () => {
    const funcDecl = makeNode(
      "function_declaration", 2, 4,
      { name: nameNode("validateCredentials") },
    );
    mockParse.mockReturnValue(fakeTree(rootWith(funcDecl)));

    const result = await findDefinition("validateCredentials", ["src/auth.ts"], opts);
    expect(result).toHaveLength(1);
    expect(result[0]).toMatchObject<Partial<SymbolDefinition>>({
      name: "validateCredentials",
      kind: "function",
      filePath: "src/auth.ts",
      line: 3, // row 2 → 1-based = 3
      column: 1,
    });
  });

  it("finds a generator_function_declaration as kind 'function'", async () => {
    const funcDecl = makeNode(
      "generator_function_declaration", 5, 10,
      { name: nameNode("genFn") },
    );
    mockParse.mockReturnValue(fakeTree(rootWith(funcDecl)));

    const [def] = await findDefinition("genFn", ["src/a.ts"], opts);
    expect(def?.kind).toBe("function");
    expect(def?.name).toBe("genFn");
  });

  it("finds a class_declaration", async () => {
    const classDecl = makeNode(
      "class_declaration", 10, 20,
      { name: nameNode("AuthService") },
    );
    mockParse.mockReturnValue(fakeTree(rootWith(classDecl)));

    const [def] = await findDefinition("AuthService", ["src/auth.ts"], opts);
    expect(def?.kind).toBe("class");
    expect(def?.name).toBe("AuthService");
    expect(def?.line).toBe(11);
  });

  it("finds an interface_declaration", async () => {
    const iface = makeNode(
      "interface_declaration", 0, 5,
      { name: nameNode("UserCredentials") },
    );
    mockParse.mockReturnValue(fakeTree(rootWith(iface)));

    const [def] = await findDefinition("UserCredentials", ["src/types.ts"], opts);
    expect(def?.kind).toBe("interface");
    expect(def?.name).toBe("UserCredentials");
  });

  it("finds a type_alias_declaration as kind 'type'", async () => {
    const typeDecl = makeNode(
      "type_alias_declaration", 3, 3,
      { name: nameNode("UserId") },
    );
    mockParse.mockReturnValue(fakeTree(rootWith(typeDecl)));

    const [def] = await findDefinition("UserId", ["src/types.ts"], opts);
    expect(def?.kind).toBe("type");
  });

  it("finds an enum_declaration as kind 'type'", async () => {
    const enumDecl = makeNode(
      "enum_declaration", 7, 12,
      { name: nameNode("Role") },
    );
    mockParse.mockReturnValue(fakeTree(rootWith(enumDecl)));

    const [def] = await findDefinition("Role", ["src/enums.ts"], opts);
    expect(def?.kind).toBe("type");
    expect(def?.name).toBe("Role");
  });

  it("finds a lexical_declaration variable_declarator as kind 'variable'", async () => {
    const declarator = makeNode(
      "variable_declarator", 6, 6,
      { name: nameNode("MAX_RETRIES") },
    );
    const lexDecl = makeNode(
      "lexical_declaration", 6, 6,
      {},
      [declarator],
    );
    lexDecl.namedChildren = [declarator];
    mockParse.mockReturnValue(fakeTree(rootWith(lexDecl)));

    const [def] = await findDefinition("MAX_RETRIES", ["src/config.ts"], opts);
    expect(def?.kind).toBe("variable");
    expect(def?.name).toBe("MAX_RETRIES");
  });

  it("finds export_statement → function_declaration", async () => {
    const funcDecl = makeNode(
      "function_declaration", 2, 4,
      { name: nameNode("validateCredentials") },
    );
    const exportStmt = makeNode(
      "export_statement", 2, 4,
      { declaration: funcDecl },
    );
    mockParse.mockReturnValue(fakeTree(rootWith(exportStmt)));

    const result = await findDefinition("validateCredentials", ["src/auth.ts"], opts);
    expect(result).toHaveLength(1);
    expect(result[0]?.kind).toBe("function");
  });

  it("includes a snippet in the result", async () => {
    const funcDecl = makeNode(
      "function_declaration", 2, 4,
      { name: nameNode("validateCredentials") },
    );
    mockParse.mockReturnValue(fakeTree(rootWith(funcDecl)));

    const [def] = await findDefinition("validateCredentials", ["src/auth.ts"], opts);
    // snippet should contain the function line (row 2)
    expect(def?.snippet).toBeDefined();
    expect(def?.snippet).toContain("validateCredentials");
  });

  it("aggregates results across multiple files", async () => {
    const makeTree = (name: string) => {
      const decl = makeNode("function_declaration", 0, 2, { name: nameNode(name) });
      return fakeTree(rootWith(decl));
    };
    mockParse
      .mockReturnValueOnce(makeTree("foo"))
      .mockReturnValueOnce(makeTree("bar"));

    const result = await findDefinition("foo", ["src/a.ts", "src/b.ts"], opts);
    // Only "foo" should match across both files
    expect(result).toHaveLength(1);
    expect(result[0]?.filePath).toBe("src/a.ts");
  });

  it("reads file from join(workspacePath, filePath)", async () => {
    mockParse.mockReturnValue(fakeTree(rootWith()));
    await findDefinition("x", ["src/auth.ts"], { workspacePath: "/my/workspace" });
    expect(mockReadFile).toHaveBeenCalledWith("/my/workspace/src/auth.ts", "utf-8");
  });

  it("JavaScript (.js) files are also supported", async () => {
    const funcDecl = makeNode(
      "function_declaration", 0, 3,
      { name: nameNode("helpFn") },
    );
    mockParse.mockReturnValue(fakeTree(rootWith(funcDecl)));

    const [def] = await findDefinition("helpFn", ["lib/helper.js"], opts);
    expect(def?.kind).toBe("function");
    expect(def?.filePath).toBe("lib/helper.js");
  });

  it("handles TypeScript extensions: .mts, .cts", async () => {
    const funcDecl = makeNode("function_declaration", 0, 2, { name: nameNode("fn") });
    mockParse.mockReturnValue(fakeTree(rootWith(funcDecl)));

    const [a] = await findDefinition("fn", ["src/a.mts"], opts);
    expect(a?.filePath).toBe("src/a.mts");
  });

  it("returns empty array when parser.parse throws", async () => {
    mockParse.mockImplementation(() => { throw new Error("parse failed"); });
    const result = await findDefinition("anything", ["src/bad.ts"], opts);
    expect(result).toEqual([]);
  });
});

// ─── findReferences ───────────────────────────────────────────────────────────

describe("findReferences()", () => {
  it("returns empty array for empty filePaths", async () => {
    const result = await findReferences("foo", [], opts);
    expect(result).toEqual([]);
    expect(mockReadFile).not.toHaveBeenCalled();
  });

  it("returns empty array when file cannot be read", async () => {
    mockReadFile.mockRejectedValue(Object.assign(new Error("ENOENT"), { code: "ENOENT" }));
    const result = await findReferences("foo", ["src/missing.ts"], opts);
    expect(result).toEqual([]);
  });

  it("returns empty array for unsupported extension", async () => {
    const result = await findReferences("foo", ["data.csv"], opts);
    expect(result).toEqual([]);
    expect(mockParse).not.toHaveBeenCalled();
  });

  it("returns empty array when no identifier matches", async () => {
    const idNode = makeNode("identifier", 1, 1, {}, [], "otherSymbol");
    const root = rootWith(idNode);
    mockParse.mockReturnValue(fakeTree(root));

    const result = await findReferences("validateCredentials", ["src/auth.ts"], opts);
    expect(result).toEqual([]);
  });

  it("finds an identifier node matching symbolName", async () => {
    const id = { ...makeNode("identifier", 5, 5), text: "validateCredentials" };
    const root = rootWith(id);
    mockParse.mockReturnValue(fakeTree(root));

    const result = await findReferences("validateCredentials", ["src/app.ts"], opts);
    expect(result).toHaveLength(1);
    expect(result[0]).toMatchObject<Partial<SymbolLocation>>({
      filePath: "src/app.ts",
      line: 6,    // row 5 → 1-based
      column: 1,  // col 0 → 1-based
    });
  });

  it("finds a type_identifier node matching symbolName", async () => {
    const id = { ...makeNode("type_identifier", 3, 3), text: "User" };
    const root = rootWith(id);
    mockParse.mockReturnValue(fakeTree(root));

    const result = await findReferences("User", ["src/app.ts"], opts);
    expect(result).toHaveLength(1);
    expect(result[0]?.line).toBe(4);
  });

  it("finds multiple identifier nodes in one file", async () => {
    const id1 = { ...makeNode("identifier", 2, 2), text: "foo" };
    const id2 = { ...makeNode("identifier", 8, 8), text: "foo" };
    const other = { ...makeNode("identifier", 5, 5), text: "bar" };
    const root = rootWith(id1, other, id2);
    mockParse.mockReturnValue(fakeTree(root));

    const result = await findReferences("foo", ["src/utils.ts"], opts);
    expect(result).toHaveLength(2);
    expect(result[0]?.line).toBe(3);
    expect(result[1]?.line).toBe(9);
  });

  it("walks deeply nested nodes to find identifiers", async () => {
    // symbol is inside a nested child structure
    const leaf = { ...makeNode("identifier", 10, 10), text: "TARGET" };
    const mid = makeNode("expression_statement", 10, 10, {}, [leaf]);
    const block = makeNode("statement_block", 9, 11, {}, [mid]);
    const root = rootWith(block);
    mockParse.mockReturnValue(fakeTree(root));

    const result = await findReferences("TARGET", ["src/deep.ts"], opts);
    expect(result).toHaveLength(1);
    expect(result[0]?.line).toBe(11);
  });

  it("includes a snippet in each reference", async () => {
    // row 2 → SOURCE_LINES[2] = "export function validateCredentials(...)"
    const id = { ...makeNode("identifier", 2, 2), text: "validateCredentials" };
    const root = rootWith(id);
    mockParse.mockReturnValue(fakeTree(root));

    const [ref] = await findReferences("validateCredentials", ["src/auth.ts"], opts);
    expect(ref?.snippet).toBeDefined();
    expect(ref?.snippet).toContain("validateCredentials");
  });

  it("snippet includes ±1 lines of context", async () => {
    // row 2; SOURCE_LINES: [0]="// line 0", [1]="// line 1", [2]="export function..."
    const id = { ...makeNode("identifier", 2, 2), text: "validateCredentials" };
    const root = rootWith(id);
    mockParse.mockReturnValue(fakeTree(root));

    const [ref] = await findReferences("validateCredentials", ["src/auth.ts"], opts);
    // snippet should contain row 1, 2, 3
    expect(ref?.snippet).toContain("// line 1");
    expect(ref?.snippet).toContain("validateCredentials");
    expect(ref?.snippet).toContain("return true");
  });

  it("aggregates references from multiple files", async () => {
    const makeRefTree = () => {
      const id = { ...makeNode("identifier", 0, 0), text: "greet" };
      return fakeTree(rootWith(id));
    };
    mockParse
      .mockReturnValueOnce(makeRefTree())
      .mockReturnValueOnce(makeRefTree());

    const result = await findReferences("greet", ["src/a.ts", "src/b.ts"], opts);
    expect(result).toHaveLength(2);
    expect(result[0]?.filePath).toBe("src/a.ts");
    expect(result[1]?.filePath).toBe("src/b.ts");
  });

  it("reads file from join(workspacePath, filePath)", async () => {
    mockParse.mockReturnValue(fakeTree(rootWith()));
    await findReferences("x", ["src/auth.ts"], { workspacePath: "/abs/root" });
    expect(mockReadFile).toHaveBeenCalledWith("/abs/root/src/auth.ts", "utf-8");
  });

  it("returns empty array when parser.parse throws", async () => {
    mockParse.mockImplementation(() => { throw new Error("parse failed"); });
    const result = await findReferences("x", ["src/bad.ts"], opts);
    expect(result).toEqual([]);
  });

  it("column is 1-based", async () => {
    const id = {
      ...makeNode("identifier", 3, 3),
      text: "myConst",
      startPosition: { row: 3, column: 6 },
    };
    const root = rootWith(id);
    mockParse.mockReturnValue(fakeTree(root));

    const [ref] = await findReferences("myConst", ["src/a.ts"], opts);
    expect(ref?.column).toBe(7); // col 6 → 1-based = 7
  });
});

// ─── SymbolDefinition interface contract ──────────────────────────────────────

describe("SymbolDefinition — interface contract", () => {
  it("contract: definition has filePath, line, column, name, kind", () => {
    const def: SymbolDefinition = {
      filePath: "src/auth/login.ts",
      line: 12,
      column: 1,
      name: "validateCredentials",
      kind: "function",
    };
    expect(typeof def.filePath).toBe("string");
    expect(def.line).toBeGreaterThanOrEqual(1);
    expect(def.column).toBeGreaterThanOrEqual(1);
    expect(typeof def.name).toBe("string");
    expect(typeof def.kind).toBe("string");
  });

  it("contract: snippet is optional", () => {
    const def: SymbolDefinition = {
      filePath: "src/x.ts",
      line: 1,
      column: 1,
      name: "foo",
      kind: "class",
    };
    expect(def.snippet).toBeUndefined();
  });

  it("contract: line is 1-based (>= 1)", () => {
    const def: SymbolDefinition = {
      filePath: "src/x.ts",
      line: 1,
      column: 1,
      name: "bar",
      kind: "interface",
    };
    expect(def.line).toBeGreaterThanOrEqual(1);
    expect(def.column).toBeGreaterThanOrEqual(1);
  });

  it("contract: kind describes the symbol type", () => {
    const validKinds = ["function", "class", "interface", "variable", "type", "import"];
    const def: SymbolDefinition = {
      filePath: "src/x.ts",
      line: 5,
      column: 1,
      name: "User",
      kind: "interface",
    };
    expect(validKinds).toContain(def.kind);
  });
});

// ─── SymbolLocation interface contract ────────────────────────────────────────

describe("SymbolLocation — interface contract", () => {
  it("contract: location has filePath, line, column", () => {
    const loc: SymbolLocation = {
      filePath: "src/app.ts",
      line: 20,
      column: 5,
    };
    expect(typeof loc.filePath).toBe("string");
    expect(loc.line).toBeGreaterThanOrEqual(1);
    expect(loc.column).toBeGreaterThanOrEqual(1);
  });

  it("contract: snippet is optional on SymbolLocation", () => {
    const loc: SymbolLocation = { filePath: "src/x.ts", line: 3, column: 1 };
    expect(loc.snippet).toBeUndefined();
  });

  it("contract: SymbolDefinition extends SymbolLocation", () => {
    const def: SymbolDefinition = {
      filePath: "src/x.ts",
      line: 1,
      column: 1,
      name: "foo",
      kind: "function",
    };
    // Verify structural compatibility
    const loc: SymbolLocation = def;
    expect(loc.filePath).toBe(def.filePath);
  });
});
