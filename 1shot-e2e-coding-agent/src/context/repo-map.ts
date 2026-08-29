/**
 * src/context/repo-map.ts — Repository map generator (FR-003, Research Decision R3)
 *
 * Walks the workspace, parses each source file with web-tree-sitter for real
 * AST-based symbol extraction (functions, classes, interfaces, types, exported
 * consts), and produces a compact text skeleton that fits within a configurable
 * token budget.
 *
 * Grammar WASM files come from tree-sitter-wasms (pre-compiled, no native
 * compilation required). A singleton Parser is initialised once; language
 * grammars are loaded and cached on first use.
 *
 * Supported languages: TypeScript, TSX, JavaScript, JSX, Python, Go, Java,
 * Kotlin, Ruby, Rust.
 *
 * Token estimation: Math.ceil(chars / 4)  — the standard ~4 chars/token rule
 * for code/English text. Accurate enough for budget enforcement.
 */

import Parser from "web-tree-sitter";
import { createRequire } from "node:module";
import { join, extname } from "node:path";
import { readdir, readFile } from "node:fs/promises";

const _require = createRequire(import.meta.url);

// ─── Types ────────────────────────────────────────────────────────────────────

export interface RepoMapSymbol {
  /** e.g. "function" | "class" | "interface" | "type" | "const" */
  kind: string;
  /** Symbol name */
  name: string;
  /** 1-based line number */
  line: number;
}

export interface RepoMapFile {
  /** Relative path from workspace root */
  path: string;
  symbols: RepoMapSymbol[];
}

export interface RepoMap {
  files: RepoMapFile[];
  /** Estimated token count for the rendered map text */
  tokenCount: number;
}

// ─── Options ──────────────────────────────────────────────────────────────────

export interface RepoMapOptions {
  /** Absolute workspace root */
  workspacePath: string;
  /** Maximum tokens to use for the map. Defaults to 5_000. */
  maxTokens?: number;
  /** Directory/path segments to ignore (e.g. ["node_modules/**", "dist/**"]). */
  ignore?: string[];
}

// ─── Source file extensions ───────────────────────────────────────────────────

/** Extensions for which tree-sitter grammars are bundled. */
const SOURCE_EXTENSIONS = new Set([
  ".ts", ".tsx", ".mts", ".cts",
  ".js", ".jsx", ".mjs", ".cjs",
  ".py",
  ".go",
  ".java",
  ".rb",
  ".rs",
  ".kt",
]);

// ─── Default ignored path segments ───────────────────────────────────────────

const DEFAULT_IGNORE_SEGMENTS = [
  "node_modules", "dist", "build", ".git", "coverage",
  "__pycache__", ".nyc_output", ".cache", "vendor",
  "out", ".next", ".nuxt",
];

// ─── Grammar file mapping ─────────────────────────────────────────────────────

/** Maps file extension → tree-sitter-wasms grammar filename. */
const EXT_TO_WASM: Record<string, string> = {
  ".ts":  "tree-sitter-typescript.wasm",
  ".mts": "tree-sitter-typescript.wasm",
  ".cts": "tree-sitter-typescript.wasm",
  ".tsx": "tree-sitter-tsx.wasm",
  ".js":  "tree-sitter-javascript.wasm",
  ".jsx": "tree-sitter-javascript.wasm",
  ".mjs": "tree-sitter-javascript.wasm",
  ".cjs": "tree-sitter-javascript.wasm",
  ".py":  "tree-sitter-python.wasm",
  ".go":  "tree-sitter-go.wasm",
  ".java":"tree-sitter-java.wasm",
  ".kt":  "tree-sitter-kotlin.wasm",
  ".rb":  "tree-sitter-ruby.wasm",
  ".rs":  "tree-sitter-rust.wasm",
};

// ─── Parser singleton ─────────────────────────────────────────────────────────

let _parser: Parser | null = null;
const _langCache = new Map<string, Parser.Language>();

/**
 * Lazily initialise the `web-tree-sitter` Parser (once per process) and load
 * the grammar for the given WASM filename, caching the result.
 * Returns the Parser instance configured for the requested language.
 */
async function configureParser(wasmFile: string): Promise<Parser> {
  if (_parser === null) {
    await Parser.init();
    _parser = new Parser();
  }
  if (!_langCache.has(wasmFile)) {
    // resolve() finds the file on disk via Node's module resolution
    const wasmPath = _require.resolve(`tree-sitter-wasms/out/${wasmFile}`);
    const lang = await Parser.Language.load(wasmPath);
    _langCache.set(wasmFile, lang);
  }
  _parser.setLanguage(_langCache.get(wasmFile)!);
  return _parser;
}

// ─── Token estimation ─────────────────────────────────────────────────────────

/** Estimate token count for text using the ~4 chars/token heuristic. */
export function estimateTokens(text: string): number {
  return Math.ceil(text.length / 4);
}

// ─── Symbol extraction ────────────────────────────────────────────────────────

/**
 * Extract top-level symbols from source text using web-tree-sitter AST parsing.
 * Unrecognised extensions return an empty list (file path is still included in
 * the repo map). The parser singleton is lazily initialised on first call.
 */
export async function extractSymbols(
  relativePath: string,
  source: string,
): Promise<RepoMapSymbol[]> {
  const ext = extname(relativePath).toLowerCase();
  const wasmFile = EXT_TO_WASM[ext];
  if (!wasmFile) return [];

  let parser: Parser;
  try {
    parser = await configureParser(wasmFile);
  } catch {
    // Grammar unavailable or WASM init failed — degrade gracefully
    return [];
  }

  const tree = parser.parse(source);
  return walkRoot(tree.rootNode, ext);
}

// ─── Language-specific AST walkers ───────────────────────────────────────────

type SyntaxNode = Parser.SyntaxNode;

/** Dispatch to the correct language walker based on file extension. */
function walkRoot(root: SyntaxNode, ext: string): RepoMapSymbol[] {
  switch (ext) {
    case ".ts": case ".tsx": case ".mts": case ".cts":
    case ".js": case ".jsx": case ".mjs": case ".cjs":
      return walkTSJS(root);
    case ".py":   return walkPython(root);
    case ".go":   return walkGo(root);
    case ".java": return walkJava(root);
    case ".rs":   return walkRust(root);
    case ".kt":   return walkKotlin(root);
    case ".rb":   return walkRuby(root);
    default:      return [];
  }
}

/**
 * TypeScript / JavaScript walker.
 *
 * Handles two patterns:
 *  1. `export_statement` wrapping a declaration — the declaration's name is
 *     taken from its `name` field (or from `variable_declarator` children
 *     for `lexical_declaration`).
 *  2. Bare top-level declarations (functions, classes, …) — `const`/`let`/
 *     `var` without `export` are intentionally skipped to keep the map
 *     focused on the public API.
 */
function walkTSJS(root: SyntaxNode): RepoMapSymbol[] {
  const symbols: RepoMapSymbol[] = [];
  for (const child of root.children) {
    if (child.type === "export_statement") {
      const decl = child.childForFieldName("declaration");
      if (decl) {
        const sym = tsJSDeclSymbol(decl);
        if (sym) symbols.push({ ...sym, line: child.startPosition.row + 1 });
      }
    } else if (child.type !== "lexical_declaration") {
      // Bare declarations (function, class, interface, …) are included;
      // bare variable declarations (const/let/var) are excluded.
      const sym = tsJSDeclSymbol(child);
      if (sym) symbols.push({ ...sym, line: child.startPosition.row + 1 });
    }
  }
  return symbols;
}

/** Extract kind+name from a TypeScript/JS declaration node. */
function tsJSDeclSymbol(node: SyntaxNode): { kind: string; name: string } | null {
  switch (node.type) {
    case "function_declaration":
    case "generator_function_declaration": {
      const name = node.childForFieldName("name")?.text;
      return name ? { kind: "function", name } : null;
    }
    case "class_declaration": {
      const name = node.childForFieldName("name")?.text;
      return name ? { kind: "class", name } : null;
    }
    case "interface_declaration": {
      const name = node.childForFieldName("name")?.text;
      return name ? { kind: "interface", name } : null;
    }
    case "type_alias_declaration": {
      const name = node.childForFieldName("name")?.text;
      return name ? { kind: "type", name } : null;
    }
    case "enum_declaration": {
      const name = node.childForFieldName("name")?.text;
      return name ? { kind: "enum", name } : null;
    }
    case "lexical_declaration": {
      // `export const NAME = …` — the name lives on the variable_declarator child
      for (const child of node.namedChildren) {
        if (child.type === "variable_declarator") {
          const name = child.childForFieldName("name")?.text;
          if (name) return { kind: "const", name };
        }
      }
      return null;
    }
    default:
      return null;
  }
}

/** Python walker: `function_definition`, `class_definition`, `decorated_definition`. */
function walkPython(root: SyntaxNode): RepoMapSymbol[] {
  const symbols: RepoMapSymbol[] = [];
  for (const child of root.children) {
    switch (child.type) {
      case "function_definition": {
        const name = child.childForFieldName("name")?.text;
        if (name) symbols.push({ kind: "function", name, line: child.startPosition.row + 1 });
        break;
      }
      case "class_definition": {
        const name = child.childForFieldName("name")?.text;
        if (name) symbols.push({ kind: "class", name, line: child.startPosition.row + 1 });
        break;
      }
      case "decorated_definition": {
        // @decorator wraps either a function_definition or class_definition
        const inner = child.namedChildren.find(
          (c) => c.type === "function_definition" || c.type === "class_definition",
        );
        if (inner) {
          const name = inner.childForFieldName("name")?.text;
          const kind = inner.type === "function_definition" ? "function" : "class";
          if (name) symbols.push({ kind, name, line: child.startPosition.row + 1 });
        }
        break;
      }
    }
  }
  return symbols;
}

/**
 * Go walker: `function_declaration`, `method_declaration`, `type_declaration`.
 *
 * Go's `type_declaration` contains one or more `type_spec` named children,
 * each of which has a `name` field (the type identifier).
 */
function walkGo(root: SyntaxNode): RepoMapSymbol[] {
  const symbols: RepoMapSymbol[] = [];
  for (const child of root.children) {
    switch (child.type) {
      case "function_declaration": {
        const name = child.childForFieldName("name")?.text;
        if (name) symbols.push({ kind: "function", name, line: child.startPosition.row + 1 });
        break;
      }
      case "method_declaration": {
        const name = child.childForFieldName("name")?.text;
        if (name) symbols.push({ kind: "function", name, line: child.startPosition.row + 1 });
        break;
      }
      case "type_declaration": {
        // type_declaration → type_spec (one or more), each has a name field
        for (const c of child.namedChildren) {
          if (c.type === "type_spec") {
            const name = c.childForFieldName("name")?.text;
            if (name) symbols.push({ kind: "type", name, line: child.startPosition.row + 1 });
          }
        }
        break;
      }
    }
  }
  return symbols;
}

/** Java walker: top-level `class_declaration`, `interface_declaration`, `enum_declaration`. */
function walkJava(root: SyntaxNode): RepoMapSymbol[] {
  const symbols: RepoMapSymbol[] = [];
  for (const child of root.children) {
    switch (child.type) {
      case "class_declaration": {
        const name = child.childForFieldName("name")?.text;
        if (name) symbols.push({ kind: "class", name, line: child.startPosition.row + 1 });
        break;
      }
      case "interface_declaration": {
        const name = child.childForFieldName("name")?.text;
        if (name) symbols.push({ kind: "interface", name, line: child.startPosition.row + 1 });
        break;
      }
      case "enum_declaration": {
        const name = child.childForFieldName("name")?.text;
        if (name) symbols.push({ kind: "enum", name, line: child.startPosition.row + 1 });
        break;
      }
    }
  }
  return symbols;
}

/**
 * Rust walker: `function_item`, `struct_item`, `enum_item`, `trait_item`, `impl_item`.
 *
 * For `impl_item`, tree-sitter exposes no single `name` field — instead we
 * collect the `type_identifier` tokens that represent the trait (optional) and
 * the implementing type, and join them as "Trait for Type" or just "Type".
 */
function walkRust(root: SyntaxNode): RepoMapSymbol[] {
  const symbols: RepoMapSymbol[] = [];
  for (const child of root.children) {
    switch (child.type) {
      case "function_item": {
        const name = child.childForFieldName("name")?.text;
        if (name) symbols.push({ kind: "function", name, line: child.startPosition.row + 1 });
        break;
      }
      case "struct_item": {
        const name = child.childForFieldName("name")?.text;
        if (name) symbols.push({ kind: "struct", name, line: child.startPosition.row + 1 });
        break;
      }
      case "enum_item": {
        const name = child.childForFieldName("name")?.text;
        if (name) symbols.push({ kind: "enum", name, line: child.startPosition.row + 1 });
        break;
      }
      case "trait_item": {
        const name = child.childForFieldName("name")?.text;
        if (name) symbols.push({ kind: "trait", name, line: child.startPosition.row + 1 });
        break;
      }
      case "impl_item": {
        // Collect type_identifier children: [TraitName, "for", TypeName] or [TypeName]
        const typeIds = child.children
          .filter((c) => c.type === "type_identifier")
          .map((c) => c.text);
        if (typeIds.length > 0) {
          const name =
            typeIds.length >= 2 ? `${typeIds[0]!} for ${typeIds[1]!}` : typeIds[0]!;
          symbols.push({ kind: "impl", name, line: child.startPosition.row + 1 });
        }
        break;
      }
    }
  }
  return symbols;
}

/**
 * Kotlin walker: `function_declaration`, `class_declaration`, `object_declaration`.
 *
 * Kotlin's tree-sitter grammar does not expose a `name` field on function or
 * class declarations — the name is a `simple_identifier` or `type_identifier`
 * direct child. For class-like declarations the first keyword child (`class`
 * vs `interface`) determines the kind.
 */
function walkKotlin(root: SyntaxNode): RepoMapSymbol[] {
  const symbols: RepoMapSymbol[] = [];
  for (const child of root.children) {
    switch (child.type) {
      case "function_declaration": {
        const nameNode = child.children.find((c) => c.type === "simple_identifier");
        if (nameNode?.text) {
          symbols.push({ kind: "function", name: nameNode.text, line: child.startPosition.row + 1 });
        }
        break;
      }
      case "class_declaration": {
        // First `class` or `interface` keyword child determines kind
        const keyword = child.children.find(
          (c) => c.type === "class" || c.type === "interface",
        );
        const kind = keyword?.type === "interface" ? "interface" : "class";
        const nameNode = child.children.find((c) => c.type === "type_identifier");
        if (nameNode?.text) {
          symbols.push({ kind, name: nameNode.text, line: child.startPosition.row + 1 });
        }
        break;
      }
      case "object_declaration": {
        const nameNode = child.children.find((c) => c.type === "type_identifier");
        if (nameNode?.text) {
          symbols.push({ kind: "object", name: nameNode.text, line: child.startPosition.row + 1 });
        }
        break;
      }
    }
  }
  return symbols;
}

/** Ruby walker: `method`, `singleton_method`, `class`, `module`. */
function walkRuby(root: SyntaxNode): RepoMapSymbol[] {
  const symbols: RepoMapSymbol[] = [];
  for (const child of root.children) {
    switch (child.type) {
      case "method":
      case "singleton_method": {
        const name = child.childForFieldName("name")?.text;
        if (name) symbols.push({ kind: "function", name, line: child.startPosition.row + 1 });
        break;
      }
      case "class": {
        const name = child.childForFieldName("name")?.text;
        if (name) symbols.push({ kind: "class", name, line: child.startPosition.row + 1 });
        break;
      }
      case "module": {
        const name = child.childForFieldName("name")?.text;
        if (name) symbols.push({ kind: "module", name, line: child.startPosition.row + 1 });
        break;
      }
    }
  }
  return symbols;
}

// ─── Path ignore check ────────────────────────────────────────────────────────

/**
 * Returns true if any ignore pattern matches a segment of `relativePath`.
 * Patterns can be glob-style ("node_modules/**") or bare ("node_modules").
 */
export function isIgnored(relativePath: string, patterns: string[]): boolean {
  const parts = relativePath.split("/");
  return patterns.some((pattern) => {
    const segment = pattern
      .replace(/\*\*/g, "")
      .split("/")
      .filter(Boolean)[0];
    if (!segment) return false;
    return parts.includes(segment) || relativePath.startsWith(segment + "/");
  });
}

// ─── generateRepoMap ──────────────────────────────────────────────────────────

/**
 * Generate a repository map by walking the workspace, extracting symbols from
 * each source file, and truncating to fit within `maxTokens`.
 *
 * Files that exceed the remaining budget are included with no symbols (path only)
 * or dropped entirely when even the path would overflow.
 */
export async function generateRepoMap(options: RepoMapOptions): Promise<RepoMap> {
  const { workspacePath, maxTokens = 5_000, ignore = [] } = options;

  const allIgnoreSegments = [...DEFAULT_IGNORE_SEGMENTS, ...ignore];

  // ── 1. Walk workspace recursively ─────────────────────────────────────────
  let allEntries: string[];
  try {
    allEntries = (await readdir(
      workspacePath,
      { recursive: true } as Parameters<typeof readdir>[1],
    )) as unknown as string[];
  } catch {
    return { files: [], tokenCount: 0 };
  }

  // ── 2. Filter to source files supported by bundled grammars, sorted ───────
  const sourcePaths = (allEntries as string[])
    .filter((p) => SOURCE_EXTENSIONS.has(extname(p).toLowerCase()))
    .filter((p) => !isIgnored(p, allIgnoreSegments))
    .sort();

  // ── 3. Extract symbols and build map within token budget ──────────────────
  const files: RepoMapFile[] = [];
  let totalTokens = 0;

  for (const relativePath of sourcePaths) {
    if (totalTokens >= maxTokens) break;

    let source = "";
    try {
      source = await readFile(join(workspacePath, relativePath), "utf-8");
    } catch {
      continue; // unreadable file — skip
    }

    const symbols = await extractSymbols(relativePath, source);
    const fileEntry: RepoMapFile = { path: relativePath, symbols };
    const rendered = renderFileEntry(fileEntry);
    const cost = estimateTokens(rendered);

    if (totalTokens + cost <= maxTokens) {
      files.push(fileEntry);
      totalTokens += cost;
    } else {
      const pathCost = estimateTokens(relativePath + "\n");
      if (totalTokens + pathCost <= maxTokens) {
        files.push({ path: relativePath, symbols: [] });
        totalTokens += pathCost;
      } else {
        break;
      }
    }
  }

  return { files, tokenCount: totalTokens };
}

// ─── Internal: render a single file entry ─────────────────────────────────────

function renderFileEntry(file: RepoMapFile): string {
  const lines: string[] = [file.path];
  for (const sym of file.symbols) {
    lines.push(`  ${sym.kind} ${sym.name} (line ${sym.line})`);
  }
  return lines.join("\n") + "\n";
}

// ─── formatRepoMap ────────────────────────────────────────────────────────────

/**
 * Render a RepoMap as a compact text skeleton suitable for injecting into a
 * system/user prompt.
 *
 * Format:
 *   src/auth/login.ts
 *     function validateCredentials (line 12)
 *     class LoginError (line 45)
 */
export function formatRepoMap(map: RepoMap): string {
  const lines: string[] = [];
  for (const file of map.files) {
    lines.push(file.path);
    for (const sym of file.symbols) {
      lines.push(`  ${sym.kind} ${sym.name} (line ${sym.line})`);
    }
  }
  return lines.join("\n");
}

