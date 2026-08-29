/**
 * src/context/symbol-nav.ts — Symbol navigation module (US2, T042)
 *
 * Uses web-tree-sitter to provide two core navigation operations:
 *
 *  findDefinition — locates where a symbol is *declared* (function, class,
 *    interface, type alias, exported const, etc.) across a set of files.
 *
 *  findReferences — locates every *usage site* of a symbol (any identifier
 *    leaf node whose text matches the symbol name) across a set of files.
 *
 * Both functions read files from disk, parse with the appropriate grammar,
 * walk the AST, and return 1-based line/column locations with a small
 * source snippet for context.
 *
 * Uses the same Parser singleton / language cache pattern as repo-map.ts and
 * chunker.ts so WASM grammars are loaded at most once per process.
 */

import Parser from "web-tree-sitter";
import { createRequire } from "node:module";
import { join, extname } from "node:path";
import { readFile } from "node:fs/promises";

const _require = createRequire(import.meta.url);

// ─── Types ────────────────────────────────────────────────────────────────────

export interface SymbolLocation {
  /** Relative path from workspace root */
  filePath: string;
  /** 1-based line number */
  line: number;
  /** 1-based column number */
  column: number;
  /** Surrounding context snippet (a few lines) */
  snippet?: string;
}

export interface SymbolDefinition extends SymbolLocation {
  /** Symbol name */
  name: string;
  /** "function" | "class" | "interface" | "variable" | "type" | "import" */
  kind: string;
}

// ─── Options ──────────────────────────────────────────────────────────────────

export interface SymbolNavOptions {
  /** Absolute workspace root */
  workspacePath: string;
}

// ─── Grammar map ──────────────────────────────────────────────────────────────

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

async function configureParser(wasmFile: string): Promise<Parser> {
  if (_parser === null) {
    await Parser.init();
    _parser = new Parser();
  }
  if (!_langCache.has(wasmFile)) {
    const wasmPath = _require.resolve(`tree-sitter-wasms/out/${wasmFile}`);
    const lang = await Parser.Language.load(wasmPath);
    _langCache.set(wasmFile, lang);
  }
  _parser.setLanguage(_langCache.get(wasmFile)!);
  return _parser;
}

// ─── findDefinition ───────────────────────────────────────────────────────────

/**
 * Look up the definition(s) of `symbolName` across the given files.
 *
 * Walks each file's AST for declaration nodes (function, class, interface,
 * type alias, exported const, etc.) whose name matches `symbolName`.
 * Returns an empty array when no definition is found.
 */
export async function findDefinition(
  symbolName: string,
  filePaths: string[],
  options: SymbolNavOptions,
): Promise<SymbolDefinition[]> {
  const results: SymbolDefinition[] = [];

  for (const filePath of filePaths) {
    const source = await readFileSafe(join(options.workspacePath, filePath));
    if (source === null) continue;

    const ext = extname(filePath).toLowerCase();
    const wasmFile = EXT_TO_WASM[ext];
    if (!wasmFile) continue;

    try {
      const parser = await configureParser(wasmFile);
      const tree = parser.parse(source);
      const defs = extractDefinitions(tree.rootNode, symbolName, source, filePath, ext);
      results.push(...defs);
    } catch {
      continue; // grammar unavailable — skip file
    }
  }

  return results;
}

// ─── findReferences ───────────────────────────────────────────────────────────

/**
 * Find all reference sites of `symbolName` across the given files.
 *
 * Recursively walks every AST node of each file and collects all leaf-level
 * identifier nodes whose text exactly matches `symbolName`. This includes
 * declaration sites as well as call / usage sites.
 * Returns an empty array when no references are found.
 */
export async function findReferences(
  symbolName: string,
  filePaths: string[],
  options: SymbolNavOptions,
): Promise<SymbolLocation[]> {
  const results: SymbolLocation[] = [];

  for (const filePath of filePaths) {
    const source = await readFileSafe(join(options.workspacePath, filePath));
    if (source === null) continue;

    const ext = extname(filePath).toLowerCase();
    const wasmFile = EXT_TO_WASM[ext];
    if (!wasmFile) continue;

    try {
      const parser = await configureParser(wasmFile);
      const tree = parser.parse(source);
      const refs = extractReferences(tree.rootNode, symbolName, source, filePath);
      results.push(...refs);
    } catch {
      continue;
    }
  }

  return results;
}

// ─── Definition extraction ────────────────────────────────────────────────────

type SyntaxNode = Parser.SyntaxNode;

/**
 * Walk the top-level AST nodes of a file and collect declaration nodes whose
 * name matches `symbolName`. Dispatches to a language-specific walker.
 */
function extractDefinitions(
  root: SyntaxNode,
  symbolName: string,
  source: string,
  filePath: string,
  ext: string,
): SymbolDefinition[] {
  switch (ext) {
    case ".ts": case ".tsx": case ".mts": case ".cts":
    case ".js": case ".jsx": case ".mjs": case ".cjs":
      return walkTSJSDefs(root, symbolName, source, filePath);
    case ".py":   return walkPythonDefs(root, symbolName, source, filePath);
    case ".go":   return walkGoDefs(root, symbolName, source, filePath);
    case ".java": return walkJavaDefs(root, symbolName, source, filePath);
    case ".rs":   return walkRustDefs(root, symbolName, source, filePath);
    case ".kt":   return walkKotlinDefs(root, symbolName, source, filePath);
    case ".rb":   return walkRubyDefs(root, symbolName, source, filePath);
    default:      return [];
  }
}

function walkTSJSDefs(
  root: SyntaxNode, symbolName: string, source: string, filePath: string,
): SymbolDefinition[] {
  const defs: SymbolDefinition[] = [];

  for (const child of root.children) {
    let decl: SyntaxNode | null = null;
    let baseRow = child.startPosition.row;

    if (child.type === "export_statement") {
      decl = child.childForFieldName("declaration") ?? null;
    } else if (
      child.type === "function_declaration" ||
      child.type === "generator_function_declaration" ||
      child.type === "class_declaration" ||
      child.type === "interface_declaration" ||
      child.type === "type_alias_declaration" ||
      child.type === "enum_declaration" ||
      child.type === "lexical_declaration" ||
      child.type === "import_statement"
    ) {
      decl = child;
    }

    if (!decl) continue;
    baseRow = decl.startPosition.row;

    const def = tsDeclToDefinition(decl, symbolName, source, filePath, baseRow);
    if (def) defs.push(def);
  }

  return defs;
}

function tsDeclToDefinition(
  node: SyntaxNode, symbolName: string, source: string, filePath: string, row: number,
): SymbolDefinition | null {
  switch (node.type) {
    case "function_declaration":
    case "generator_function_declaration": {
      const name = node.childForFieldName("name")?.text;
      if (name !== symbolName) return null;
      return makeDef(filePath, name, "function", row, node.startPosition.column, source);
    }
    case "class_declaration": {
      const name = node.childForFieldName("name")?.text;
      if (name !== symbolName) return null;
      return makeDef(filePath, name, "class", row, node.startPosition.column, source);
    }
    case "interface_declaration": {
      const name = node.childForFieldName("name")?.text;
      if (name !== symbolName) return null;
      return makeDef(filePath, name, "interface", row, node.startPosition.column, source);
    }
    case "type_alias_declaration": {
      const name = node.childForFieldName("name")?.text;
      if (name !== symbolName) return null;
      return makeDef(filePath, name, "type", row, node.startPosition.column, source);
    }
    case "enum_declaration": {
      const name = node.childForFieldName("name")?.text;
      if (name !== symbolName) return null;
      return makeDef(filePath, name, "type", row, node.startPosition.column, source);
    }
    case "lexical_declaration": {
      for (const child of node.namedChildren) {
        if (child.type === "variable_declarator") {
          const name = child.childForFieldName("name")?.text;
          if (name === symbolName) {
            return makeDef(filePath, name, "variable", row, node.startPosition.column, source);
          }
        }
      }
      return null;
    }
    case "import_statement": {
      // import { symbolName } from "..."  or  import symbolName from "..."
      for (const child of walkAll(node)) {
        if (
          (child.type === "identifier" || child.type === "imported_identifier") &&
          child.text === symbolName
        ) {
          return makeDef(filePath, symbolName, "import", row, child.startPosition.column, source);
        }
      }
      return null;
    }
    default:
      return null;
  }
}

function walkPythonDefs(
  root: SyntaxNode, symbolName: string, source: string, filePath: string,
): SymbolDefinition[] {
  const defs: SymbolDefinition[] = [];
  for (const child of root.children) {
    let target = child;
    if (child.type === "decorated_definition") {
      const inner = child.namedChildren.find(
        (c) => c.type === "function_definition" || c.type === "class_definition",
      );
      if (!inner) continue;
      target = inner;
    }
    if (target.type === "function_definition") {
      const name = target.childForFieldName("name")?.text;
      if (name === symbolName) defs.push(makeDef(filePath, name, "function", target.startPosition.row, target.startPosition.column, source));
    } else if (target.type === "class_definition") {
      const name = target.childForFieldName("name")?.text;
      if (name === symbolName) defs.push(makeDef(filePath, name, "class", target.startPosition.row, target.startPosition.column, source));
    }
  }
  return defs;
}

function walkGoDefs(
  root: SyntaxNode, symbolName: string, source: string, filePath: string,
): SymbolDefinition[] {
  const defs: SymbolDefinition[] = [];
  for (const child of root.children) {
    if (child.type === "function_declaration" || child.type === "method_declaration") {
      const name = child.childForFieldName("name")?.text;
      if (name === symbolName) defs.push(makeDef(filePath, name, "function", child.startPosition.row, child.startPosition.column, source));
    } else if (child.type === "type_declaration") {
      for (const c of child.namedChildren) {
        if (c.type === "type_spec") {
          const name = c.childForFieldName("name")?.text;
          if (name === symbolName) defs.push(makeDef(filePath, name, "type", child.startPosition.row, c.startPosition.column, source));
        }
      }
    }
  }
  return defs;
}

function walkJavaDefs(
  root: SyntaxNode, symbolName: string, source: string, filePath: string,
): SymbolDefinition[] {
  const defs: SymbolDefinition[] = [];
  for (const child of root.children) {
    if (child.type === "class_declaration") {
      const name = child.childForFieldName("name")?.text;
      if (name === symbolName) defs.push(makeDef(filePath, name, "class", child.startPosition.row, child.startPosition.column, source));
    } else if (child.type === "interface_declaration") {
      const name = child.childForFieldName("name")?.text;
      if (name === symbolName) defs.push(makeDef(filePath, name, "interface", child.startPosition.row, child.startPosition.column, source));
    } else if (child.type === "enum_declaration") {
      const name = child.childForFieldName("name")?.text;
      if (name === symbolName) defs.push(makeDef(filePath, name, "type", child.startPosition.row, child.startPosition.column, source));
    }
  }
  return defs;
}

function walkRustDefs(
  root: SyntaxNode, symbolName: string, source: string, filePath: string,
): SymbolDefinition[] {
  const defs: SymbolDefinition[] = [];
  for (const child of root.children) {
    if (child.type === "function_item") {
      const name = child.childForFieldName("name")?.text;
      if (name === symbolName) defs.push(makeDef(filePath, name, "function", child.startPosition.row, child.startPosition.column, source));
    } else if (child.type === "struct_item") {
      const name = child.childForFieldName("name")?.text;
      if (name === symbolName) defs.push(makeDef(filePath, name, "class", child.startPosition.row, child.startPosition.column, source));
    } else if (child.type === "enum_item") {
      const name = child.childForFieldName("name")?.text;
      if (name === symbolName) defs.push(makeDef(filePath, name, "type", child.startPosition.row, child.startPosition.column, source));
    } else if (child.type === "trait_item") {
      const name = child.childForFieldName("name")?.text;
      if (name === symbolName) defs.push(makeDef(filePath, name, "interface", child.startPosition.row, child.startPosition.column, source));
    }
  }
  return defs;
}

function walkKotlinDefs(
  root: SyntaxNode, symbolName: string, source: string, filePath: string,
): SymbolDefinition[] {
  const defs: SymbolDefinition[] = [];
  for (const child of root.children) {
    if (child.type === "function_declaration") {
      const nameNode = child.children.find((c) => c.type === "simple_identifier");
      if (nameNode?.text === symbolName) defs.push(makeDef(filePath, symbolName, "function", child.startPosition.row, child.startPosition.column, source));
    } else if (child.type === "class_declaration") {
      const nameNode = child.children.find((c) => c.type === "type_identifier");
      if (nameNode?.text === symbolName) defs.push(makeDef(filePath, symbolName, "class", child.startPosition.row, child.startPosition.column, source));
    }
  }
  return defs;
}

function walkRubyDefs(
  root: SyntaxNode, symbolName: string, source: string, filePath: string,
): SymbolDefinition[] {
  const defs: SymbolDefinition[] = [];
  for (const child of root.children) {
    if (child.type === "method" || child.type === "singleton_method") {
      const name = child.childForFieldName("name")?.text;
      if (name === symbolName) defs.push(makeDef(filePath, name, "function", child.startPosition.row, child.startPosition.column, source));
    } else if (child.type === "class") {
      const name = child.childForFieldName("name")?.text;
      if (name === symbolName) defs.push(makeDef(filePath, name, "class", child.startPosition.row, child.startPosition.column, source));
    } else if (child.type === "module") {
      const name = child.childForFieldName("name")?.text;
      if (name === symbolName) defs.push(makeDef(filePath, name, "class", child.startPosition.row, child.startPosition.column, source));
    }
  }
  return defs;
}

// ─── Reference extraction ─────────────────────────────────────────────────────

/**
 * Recursively walk every AST node and collect leaf identifier nodes whose
 * text matches `symbolName`. Works language-agnostically by matching any
 * node type containing "identifier" or equal to "constant" (Ruby) or
 * "simple_identifier" (Kotlin).
 */
function extractReferences(
  root: SyntaxNode,
  symbolName: string,
  source: string,
  filePath: string,
): SymbolLocation[] {
  const locations: SymbolLocation[] = [];
  const IDENT_RE = /identifier|constant/i;

  function walk(node: SyntaxNode) {
    if (IDENT_RE.test(node.type) && node.text === symbolName) {
      locations.push({
        filePath,
        line: node.startPosition.row + 1,
        column: node.startPosition.column + 1,
        snippet: extractSnippet(source, node.startPosition.row),
      });
    }
    for (const child of node.children) {
      walk(child);
    }
  }

  walk(root);
  return locations;
}

// ─── Shared helpers ───────────────────────────────────────────────────────────

/** Build a SymbolDefinition from raw AST position info. */
function makeDef(
  filePath: string,
  name: string,
  kind: string,
  row: number,
  col: number,
  source: string,
): SymbolDefinition {
  return {
    filePath,
    name,
    kind,
    line: row + 1,
    column: col + 1,
    snippet: extractSnippet(source, row),
  };
}

/** Extract ~3 lines of context around `lineIndex` (0-based). */
function extractSnippet(source: string, lineIndex: number): string {
  const lines = source.split("\n");
  const start = Math.max(0, lineIndex - 1);
  const end = Math.min(lines.length - 1, lineIndex + 1);
  return lines.slice(start, end + 1).join("\n");
}

/** Read a file safely — returns null on any I/O error. */
async function readFileSafe(absolutePath: string): Promise<string | null> {
  try {
    return await readFile(absolutePath, "utf-8");
  } catch {
    return null;
  }
}

/** Generator: yields a node and all its descendants in pre-order. */
function* walkAll(node: SyntaxNode): Generator<SyntaxNode> {
  yield node;
  for (const child of node.children) {
    yield* walkAll(child);
  }
}
