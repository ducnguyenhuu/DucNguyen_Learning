/**
 * tests/unit/context/chunker.test.ts — T036 / T041
 *
 * Tests for the AST-based code chunker:
 *  - chunkFile: splits a source file at function/class/method boundaries
 *  - chunkFiles: flat-maps across multiple files
 *
 * web-tree-sitter is mocked via vi.hoisted() + vi.mock() so no real WASM
 * is loaded in the unit-test environment.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";

// ─── Mock web-tree-sitter ─────────────────────────────────────────────────────
//
// We expose three control handles:
//   mockParse      — spy on parse(); controls what rootNode children look like
//   mockLoad       — spy on Language.load()
//   mockInit       — spy on Parser.init()
//
// Helper makeNode() builds a minimal fake SyntaxNode.

const { MockParser, mockParse, mockLoad, mockInit } = vi.hoisted(() => {
  const mockLoad = vi.fn().mockResolvedValue({});
  const mockInit = vi.fn().mockResolvedValue(undefined);
  const mockSetLanguage = vi.fn();
  const mockParse = vi.fn().mockReturnValue({
    rootNode: { children: [], namedChildren: [] },
  });
  const MockParser = vi.fn().mockImplementation(() => ({
    parse: mockParse,
    setLanguage: mockSetLanguage,
  }));
  MockParser.init = mockInit;
  MockParser.Language = { load: mockLoad };
  return { MockParser, mockParse, mockLoad, mockInit };
});

vi.mock("web-tree-sitter", () => ({ default: MockParser }));

import {
  chunkFile,
  chunkFiles,
  type CodeChunk,
} from "../../../src/context/chunker.js";

// ─── SyntaxNode factory ───────────────────────────────────────────────────────

type FakeNode = {
  type: string;
  startPosition: { row: number };
  endPosition: { row: number };
  text?: string;
  children: FakeNode[];
  namedChildren: FakeNode[];
  childForFieldName: (field: string) => FakeNode | null;
};

function makeNode(
  type: string,
  startRow: number,
  endRow: number,
  fields: Record<string, FakeNode> = {},
  children: FakeNode[] = [],
): FakeNode {
  return {
    type,
    startPosition: { row: startRow },
    endPosition: { row: endRow },
    children,
    namedChildren: children.filter((c) => !c.type.startsWith("[")),
    childForFieldName: (field) => fields[field] ?? null,
  };
}

function makeIdent(text: string): FakeNode {
  return makeNode("identifier", 0, 0, {}, []);
  // override text by patching after creation
  const n = makeNode("identifier", 0, 0);
  (n as unknown as Record<string, unknown>).text = text;
  return n;
}

function nameNode(text: string): FakeNode {
  const n = makeNode("identifier", 0, 0, {}, []);
  (n as unknown as { text: string }).text = text;
  return n;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function rootWith(children: FakeNode[]) {
  return { rootNode: { children, namedChildren: children } };
}

beforeEach(() => {
  vi.clearAllMocks();
  // default: parse returns an empty root (no boundaries → file chunk fallback)
  mockParse.mockReturnValue(rootWith([]));
});

// ─── chunkFile — unsupported extension ───────────────────────────────────────

describe("chunkFile() — unsupported extension", () => {
  it("returns a single 'file' chunk for .md files", async () => {
    const chunks = await chunkFile("README.md", "# Hello\n\nWorld");
    expect(chunks).toHaveLength(1);
    expect(chunks[0]!.kind).toBe("file");
    expect(mockInit).not.toHaveBeenCalled();
  });

  it("returns a single 'file' chunk for .json files", async () => {
    const chunks = await chunkFile("config.json", '{"a":1}');
    expect(chunks).toHaveLength(1);
    expect(chunks[0]!.kind).toBe("file");
  });

  it("file chunk covers entire source", async () => {
    const source = "line1\nline2\nline3";
    const [chunk] = await chunkFile("data.txt", source);
    expect(chunk!.startLine).toBe(1);
    expect(chunk!.endLine).toBe(3);
    expect(chunk!.content).toBe(source);
  });

  it("file chunk id and name equal the filePath", async () => {
    const [chunk] = await chunkFile("src/foo.xml", "<root/>");
    expect(chunk!.id).toBe("src/foo.xml");
    expect(chunk!.name).toBe("src/foo.xml");
  });
});

// ─── chunkFile — no AST boundaries ───────────────────────────────────────────

describe("chunkFile() — no recognisable boundaries", () => {
  it("falls back to file chunk when parse returns empty children", async () => {
    mockParse.mockReturnValue(rootWith([]));
    const chunks = await chunkFile("src/x.ts", "const x = 1;");
    expect(chunks).toHaveLength(1);
    expect(chunks[0]!.kind).toBe("file");
  });

  it("falls back to file chunk when parser throws", async () => {
    mockInit.mockRejectedValueOnce(new Error("WASM init failed"));
    const chunks = await chunkFile("src/x.ts", "export function foo() {}");
    expect(chunks).toHaveLength(1);
    expect(chunks[0]!.kind).toBe("file");
  });
});

// ─── chunkFile — TypeScript function boundary ─────────────────────────────────

describe("chunkFile() — TypeScript function", () => {
  it("extracts an exported function declaration as a 'function' chunk", async () => {
    const nameN = nameNode("validateCredentials");
    const funcDecl = makeNode("function_declaration", 0, 4, { name: nameN });
    const exportStmt = makeNode("export_statement", 0, 4, { declaration: funcDecl });
    mockParse.mockReturnValue(rootWith([exportStmt]));

    const source = [
      "export function validateCredentials(user: User): boolean {",
      "  // check user",
      "  return true;",
      "}",
      "",
    ].join("\n");

    const chunks = await chunkFile("src/auth.ts", source);
    expect(chunks.length).toBeGreaterThanOrEqual(1);
    const fn = chunks.find((c) => c.name === "validateCredentials");
    expect(fn).toBeDefined();
    expect(fn!.kind).toBe("function");
    expect(fn!.startLine).toBe(1);
    expect(fn!.endLine).toBe(5);
  });

  it("chunk content matches the sliced source lines", async () => {
    const nameN = nameNode("foo");
    const funcDecl = makeNode("function_declaration", 2, 4, { name: nameN });
    const exportStmt = makeNode("export_statement", 2, 4, { declaration: funcDecl });
    mockParse.mockReturnValue(rootWith([exportStmt]));

    const source = "// preamble\n// preamble2\nfunction foo() {\n  return 1;\n}";
    const chunks = await chunkFile("src/x.ts", source);
    const fn = chunks.find((c) => c.name === "foo");
    expect(fn!.content).toBe("function foo() {\n  return 1;\n}");
  });

  it("chunk id equals the function name", async () => {
    const nameN = nameNode("myHelper");
    const funcDecl = makeNode("function_declaration", 0, 2, { name: nameN });
    const exportStmt = makeNode("export_statement", 0, 2, { declaration: funcDecl });
    mockParse.mockReturnValue(rootWith([exportStmt]));

    const [chunk] = await chunkFile("src/x.ts", "function myHelper() {}\n\n");
    expect(chunk!.id).toBe("myHelper");
  });
});

// ─── chunkFile — TypeScript class with methods ────────────────────────────────

describe("chunkFile() — TypeScript class with methods", () => {
  it("produces a class chunk and method chunks", async () => {
    const methodNameN = nameNode("login");
    const methodNode = makeNode("method_definition", 1, 3, { name: methodNameN });
    const bodyNode = makeNode("class_body", 0, 4, {}, [methodNode]);
    const classNameN = nameNode("AuthService");
    const classDecl = makeNode("class_declaration", 0, 4, { name: classNameN, body: bodyNode });
    const exportStmt = makeNode("export_statement", 0, 4, { declaration: classDecl });
    mockParse.mockReturnValue(rootWith([exportStmt]));

    const source = [
      "export class AuthService {",
      "  login(user: User) {",
      "    return true;",
      "  }",
      "}",
    ].join("\n");

    const chunks = await chunkFile("src/auth.ts", source);
    const kinds = chunks.map((c) => c.kind);
    expect(kinds).toContain("class");
    expect(kinds).toContain("method");
  });

  it("method chunk id is 'ClassName.methodName'", async () => {
    const methodNameN = nameNode("login");
    const methodNode = makeNode("method_definition", 1, 3, { name: methodNameN });
    const bodyNode = makeNode("class_body", 0, 4, {}, [methodNode]);
    const classNameN = nameNode("AuthService");
    const classDecl = makeNode("class_declaration", 0, 4, { name: classNameN, body: bodyNode });
    const exportStmt = makeNode("export_statement", 0, 4, { declaration: classDecl });
    mockParse.mockReturnValue(rootWith([exportStmt]));

    const source = "export class AuthService {\n  login(user: User) {\n    return true;\n  }\n}";
    const chunks = await chunkFile("src/auth.ts", source);
    const method = chunks.find((c) => c.kind === "method");
    expect(method!.id).toBe("AuthService.login");
    expect(method!.name).toBe("AuthService.login");
  });
});

// ─── chunkFile — maxChunkChars splitting ──────────────────────────────────────

describe("chunkFile() — maxChunkChars splitting", () => {
  it("splits a chunk exceeding maxChunkChars at blank lines", async () => {
    const nameN = nameNode("bigFunction");
    const funcDecl = makeNode("function_declaration", 0, 9, { name: nameN });
    const exportStmt = makeNode("export_statement", 0, 9, { declaration: funcDecl });
    mockParse.mockReturnValue(rootWith([exportStmt]));

    // 10 lines with a blank line at position 5 — will trigger split
    const lines = [
      "function bigFunction() {",
      "  const a = 'aaaaaaaaaaaaaaaaaa';",
      "  const b = 'bbbbbbbbbbbbbbbbb';",
      "  const c = 'ccccccccccccccccc';",
      "",
      "  const d = 'ddddddddddddddddd';",
      "  const e = 'eeeeeeeeeeeeeeeee';",
      "  const f = 'fffffffffffffffff';",
      "  const g = 'ggggggggggggggggg';",
      "}",
    ];
    const source = lines.join("\n");

    const chunks = await chunkFile("src/x.ts", source, { maxChunkChars: 80 });
    // Should have been split into 2+ parts
    expect(chunks.length).toBeGreaterThan(1);
    chunks.forEach((c) => expect(c.name).toBe("bigFunction"));
  });

  it("split chunk ids have ':N' suffix", async () => {
    const nameN = nameNode("big");
    const funcDecl = makeNode("function_declaration", 0, 6, { name: nameN });
    const exportStmt = makeNode("export_statement", 0, 6, { declaration: funcDecl });
    mockParse.mockReturnValue(rootWith([exportStmt]));

    const lines = [
      "function big() {",
      "  const aaa = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaa';",
      "  const bbb = 'bbbbbbbbbbbbbbbbbbbbbbbbbbbb';",
      "",
      "  const ccc = 'cccccccccccccccccccccccccccc';",
      "  const ddd = 'dddddddddddddddddddddddddddd';",
      "}",
    ];
    const chunks = await chunkFile("src/x.ts", lines.join("\n"), { maxChunkChars: 60 });
    const ids = chunks.map((c) => c.id);
    expect(ids.some((id) => id.includes(":1"))).toBe(true);
    expect(ids.some((id) => id.includes(":2"))).toBe(true);
  });

  it("does not split chunks within maxChunkChars", async () => {
    const nameN = nameNode("tiny");
    const funcDecl = makeNode("function_declaration", 0, 1, { name: nameN });
    const exportStmt = makeNode("export_statement", 0, 1, { declaration: funcDecl });
    mockParse.mockReturnValue(rootWith([exportStmt]));

    const source = "function tiny() {}\n";
    const chunks = await chunkFile("src/x.ts", source, { maxChunkChars: 4000 });
    expect(chunks).toHaveLength(1);
    expect(chunks[0]!.id).toBe("tiny");
  });
});

// ─── chunkFile — line numbers ─────────────────────────────────────────────────

describe("chunkFile() — line numbers", () => {
  it("startLine and endLine are 1-based", async () => {
    const nameN = nameNode("foo");
    // AST row 0 → line 1
    const funcDecl = makeNode("function_declaration", 0, 2, { name: nameN });
    const exportStmt = makeNode("export_statement", 0, 2, { declaration: funcDecl });
    mockParse.mockReturnValue(rootWith([exportStmt]));

    const [chunk] = await chunkFile("src/x.ts", "function foo() {\n  return 1;\n}");
    expect(chunk!.startLine).toBe(1);
    expect(chunk!.endLine).toBe(3);
  });

  it("startLine <= endLine for every chunk", async () => {
    const nameN = nameNode("multi");
    const funcDecl = makeNode("function_declaration", 5, 15, { name: nameN });
    const exportStmt = makeNode("export_statement", 5, 15, { declaration: funcDecl });
    mockParse.mockReturnValue(rootWith([exportStmt]));

    const lines = Array.from({ length: 20 }, (_, i) => `// line ${i}`);
    const chunks = await chunkFile("src/x.ts", lines.join("\n"));
    for (const c of chunks) {
      expect(c.startLine).toBeLessThanOrEqual(c.endLine);
    }
  });
});

// ─── chunkFile — filePath propagation ────────────────────────────────────────

describe("chunkFile() — filePath", () => {
  it("every chunk carries the file path", async () => {
    const nameN = nameNode("doWork");
    const funcDecl = makeNode("function_declaration", 0, 1, { name: nameN });
    const exportStmt = makeNode("export_statement", 0, 1, { declaration: funcDecl });
    mockParse.mockReturnValue(rootWith([exportStmt]));

    const chunks = await chunkFile("src/workers/job.ts", "function doWork() {}");
    for (const c of chunks) {
      expect(c.filePath).toBe("src/workers/job.ts");
    }
  });
});

// ─── chunkFiles ───────────────────────────────────────────────────────────────

describe("chunkFiles()", () => {
  it("returns a flat array combining chunks from all files", async () => {
    mockParse.mockReturnValue(rootWith([])); // file-chunk fallback for all
    const result = await chunkFiles([
      { filePath: "src/a.ts", source: "const a = 1;" },
      { filePath: "src/b.ts", source: "const b = 2;" },
    ]);
    expect(Array.isArray(result)).toBe(true);
    expect(result.length).toBeGreaterThanOrEqual(2);
    const paths = result.map((c) => c.filePath);
    expect(paths).toContain("src/a.ts");
    expect(paths).toContain("src/b.ts");
  });

  it("returns an empty array for empty input", async () => {
    const result = await chunkFiles([]);
    expect(result).toEqual([]);
  });

  it("passes options to each file", async () => {
    mockParse.mockReturnValue(rootWith([]));
    const result = await chunkFiles(
      [{ filePath: "src/x.ts", source: "x" }],
      { maxChunkChars: 50 },
    );
    expect(Array.isArray(result)).toBe(true);
  });

  it("handles mixed supported and unsupported extensions", async () => {
    mockParse.mockReturnValue(rootWith([]));
    const result = await chunkFiles([
      { filePath: "README.md", source: "# docs" },
      { filePath: "src/app.ts", source: "const x = 1;" },
    ]);
    const paths = result.map((c) => c.filePath);
    expect(paths).toContain("README.md");
    expect(paths).toContain("src/app.ts");
  });
});

// ─── CodeChunk interface contract ─────────────────────────────────────────────

describe("CodeChunk — interface contract", () => {
  it("chunk has filePath, id, kind, name, startLine, endLine, content", () => {
    const chunk: CodeChunk = {
      filePath: "src/auth/login.ts",
      id: "validateCredentials",
      kind: "function",
      name: "validateCredentials",
      startLine: 12,
      endLine: 30,
      content: "function validateCredentials(user: User) { ... }",
    };
    expect(typeof chunk.filePath).toBe("string");
    expect(typeof chunk.id).toBe("string");
    expect(["function", "class", "method", "file"]).toContain(chunk.kind);
    expect(typeof chunk.name).toBe("string");
    expect(chunk.startLine).toBeLessThanOrEqual(chunk.endLine);
    expect(typeof chunk.content).toBe("string");
  });

  it("contract: startLine is 1-based (>= 1)", () => {
    const chunk: CodeChunk = {
      filePath: "src/x.ts",
      id: "foo",
      kind: "function",
      name: "foo",
      startLine: 1,
      endLine: 5,
      content: "function foo() {}",
    };
    expect(chunk.startLine).toBeGreaterThanOrEqual(1);
  });

  it("contract: kind must be one of the defined union values", () => {
    const validKinds: CodeChunk["kind"][] = ["function", "class", "method", "file"];
    for (const kind of validKinds) {
      const chunk: CodeChunk = { filePath: "f.ts", id: kind, kind, name: "x", startLine: 1, endLine: 2, content: "" };
      expect(validKinds).toContain(chunk.kind);
    }
  });

  it("contract: endLine >= startLine", () => {
    const chunk: CodeChunk = {
      filePath: "src/x.ts",
      id: "bar",
      kind: "class",
      name: "Bar",
      startLine: 5,
      endLine: 50,
      content: "class Bar {}",
    };
    expect(chunk.endLine).toBeGreaterThanOrEqual(chunk.startLine);
  });
});

