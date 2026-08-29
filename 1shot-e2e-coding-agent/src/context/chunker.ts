/**
 * src/context/chunker.ts — AST-based code chunker (US2, T041)
 *
 * Splits source files into semantically meaningful chunks at function/class
 * boundaries using web-tree-sitter. Chunks are the unit of embedding and
 * semantic search fed into the vectra index (T044).
 *
 * Strategy:
 *  1. Parse the file with the appropriate language grammar.
 *  2. Walk top-level AST nodes and collect function/class/method boundaries.
 *  3. Each boundary becomes a CodeChunk whose content is the exact source
 *     slice between startLine and endLine.
 *  4. Chunks larger than maxChunkChars are split on blank-line boundaries so
 *     they fit in the embedding model's context window.
 *  5. Files with no recognised boundaries fall back to a single "file" chunk.
 *  6. Unsupported extensions also produce a single "file" chunk (no AST).
 *
 * Shares the same Parser singleton / language cache pattern as repo-map.ts.
 */

import Parser from "web-tree-sitter";
import { createRequire } from "node:module";
import { extname } from "node:path";

const _require = createRequire(import.meta.url);

// ─── Types ────────────────────────────────────────────────────────────────────

export interface CodeChunk {
  /** Relative path from workspace root */
  filePath: string;
  /** Chunk identifier within the file, e.g. "MyClass.myMethod" */
  id: string;
  /** The kind of boundary: "function" | "class" | "method" | "file" */
  kind: "function" | "class" | "method" | "file";
  /** The symbol name, e.g. "validateCredentials" */
  name: string;
  /** 1-based start line */
  startLine: number;
  /** 1-based end line */
  endLine: number;
  /** Extracted source text for this chunk */
  content: string;
}

// ─── Options ──────────────────────────────────────────────────────────────────

export interface ChunkOptions {
  /** Maximum number of characters per chunk before splitting further. Default: 4000. */
  maxChunkChars?: number;
}

// ─── Grammar map (mirrors repo-map.ts) ───────────────────────────────────────

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

// ─── Raw boundary extracted from AST ─────────────────────────────────────────

interface Boundary {
  kind: "function" | "class" | "method";
  name: string;
  startLine: number; // 1-based
  endLine: number;   // 1-based
}

// ─── chunkFile ────────────────────────────────────────────────────────────────

/**
 * Parse a single source file with tree-sitter and split it into chunks at
 * function/class/method boundaries.
 *
 * Files whose extension has no grammar fall back to a single "file" chunk.
 * Files whose AST yields no top-level boundaries also produce a single "file" chunk.
 */
export async function chunkFile(
  filePath: string,
  source: string,
  options?: ChunkOptions,
): Promise<CodeChunk[]> {
  const maxChunkChars = options?.maxChunkChars ?? 4000;
  const ext = extname(filePath).toLowerCase();
  const wasmFile = EXT_TO_WASM[ext];

  // ── No grammar for this extension — single file chunk ─────────────────────
  if (!wasmFile) {
    return [makeFileChunk(filePath, source)];
  }

  // ── Parse with tree-sitter ─────────────────────────────────────────────────
  let boundaries: Boundary[];
  try {
    const parser = await configureParser(wasmFile);
    const tree = parser.parse(source);
    boundaries = extractBoundaries(tree.rootNode, ext);
  } catch {
    // Grammar failure — fall back to single file chunk
    return [makeFileChunk(filePath, source)];
  }

  // ── No recognisable boundaries — single file chunk ─────────────────────────
  if (boundaries.length === 0) {
    return [makeFileChunk(filePath, source)];
  }

  // ── Slice source lines for each boundary ───────────────────────────────────
  const lines = source.split("\n");
  const chunks: CodeChunk[] = [];

  for (const b of boundaries) {
    const sliceLines = lines.slice(b.startLine - 1, b.endLine);
    const content = sliceLines.join("\n");

    if (content.length <= maxChunkChars) {
      chunks.push({
        filePath,
        id: b.name,
        kind: b.kind,
        name: b.name,
        startLine: b.startLine,
        endLine: b.endLine,
        content,
      });
    } else {
      // Split oversized chunk on blank lines
      const subChunks = splitOnBlankLines(
        filePath, b.name, b.kind, sliceLines, b.startLine, maxChunkChars,
      );
      chunks.push(...subChunks);
    }
  }

  return chunks;
}

// ─── chunkFiles ───────────────────────────────────────────────────────────────

/**
 * Convenience helper: chunk multiple files and return a flat array of all chunks.
 */
export async function chunkFiles(
  files: Array<{ filePath: string; source: string }>,
  options?: ChunkOptions,
): Promise<CodeChunk[]> {
  const results = await Promise.all(
    files.map(({ filePath, source }) => chunkFile(filePath, source, options)),
  );
  return results.flat();
}

// ─── Boundary extraction ──────────────────────────────────────────────────────

type SyntaxNode = Parser.SyntaxNode;

/**
 * Walk the root AST node and extract top-level function/class/method boundaries.
 */
function extractBoundaries(root: SyntaxNode, ext: string): Boundary[] {
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

// ─── Language walkers ─────────────────────────────────────────────────────────

/**
 * TypeScript/JavaScript: exported and bare function/class declarations.
 * For classes, also collect method children.
 */
function walkTSJS(root: SyntaxNode): Boundary[] {
  const boundaries: Boundary[] = [];

  for (const child of root.children) {
    let decl: SyntaxNode | null = null;

    if (child.type === "export_statement") {
      decl = child.childForFieldName("declaration") ?? null;
    } else if (
      child.type === "function_declaration" ||
      child.type === "generator_function_declaration" ||
      child.type === "class_declaration"
    ) {
      decl = child;
    }

    if (!decl) continue;

    if (decl.type === "function_declaration" || decl.type === "generator_function_declaration") {
      const name = decl.childForFieldName("name")?.text;
      if (name) boundaries.push(nodeBoundary(decl, "function", name));
    } else if (decl.type === "class_declaration") {
      const name = decl.childForFieldName("name")?.text;
      if (name) {
        boundaries.push(nodeBoundary(decl, "class", name));
        const body = decl.childForFieldName("body");
        if (body) {
          for (const member of body.children) {
            if (member.type === "method_definition") {
              const methodName = member.childForFieldName("name")?.text;
              if (methodName) {
                boundaries.push(nodeBoundary(member, "method", `${name}.${methodName}`));
              }
            }
          }
        }
      }
    }
  }

  return boundaries;
}

/** Python: function_definition, class_definition (+ method children). */
function walkPython(root: SyntaxNode): Boundary[] {
  const boundaries: Boundary[] = [];

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
      if (name) boundaries.push(nodeBoundary(target, "function", name));
    } else if (target.type === "class_definition") {
      const name = target.childForFieldName("name")?.text;
      if (name) {
        boundaries.push(nodeBoundary(target, "class", name));
        const body = target.childForFieldName("body");
        if (body) {
          for (const member of body.children) {
            if (member.type === "function_definition") {
              const methodName = member.childForFieldName("name")?.text;
              if (methodName) {
                boundaries.push(nodeBoundary(member, "method", `${name}.${methodName}`));
              }
            }
          }
        }
      }
    }
  }

  return boundaries;
}

/** Go: function_declaration and method_declaration. */
function walkGo(root: SyntaxNode): Boundary[] {
  const boundaries: Boundary[] = [];
  for (const child of root.children) {
    if (child.type === "function_declaration") {
      const name = child.childForFieldName("name")?.text;
      if (name) boundaries.push(nodeBoundary(child, "function", name));
    } else if (child.type === "method_declaration") {
      const name = child.childForFieldName("name")?.text;
      if (name) boundaries.push(nodeBoundary(child, "method", name));
    }
  }
  return boundaries;
}

/** Java: class_declaration, interface_declaration + method children. */
function walkJava(root: SyntaxNode): Boundary[] {
  const boundaries: Boundary[] = [];
  for (const child of root.children) {
    if (child.type === "class_declaration" || child.type === "interface_declaration") {
      const name = child.childForFieldName("name")?.text;
      if (name) {
        boundaries.push(nodeBoundary(child, "class", name));
        const body = child.childForFieldName("body");
        if (body) {
          for (const member of body.children) {
            if (member.type === "method_declaration") {
              const methodName = member.childForFieldName("name")?.text;
              if (methodName) {
                boundaries.push(nodeBoundary(member, "method", `${name}.${methodName}`));
              }
            }
          }
        }
      }
    }
  }
  return boundaries;
}

/** Rust: function_item, impl_item (collects method fn children). */
function walkRust(root: SyntaxNode): Boundary[] {
  const boundaries: Boundary[] = [];
  for (const child of root.children) {
    if (child.type === "function_item") {
      const name = child.childForFieldName("name")?.text;
      if (name) boundaries.push(nodeBoundary(child, "function", name));
    } else if (child.type === "impl_item") {
      const typeIds = child.children
        .filter((c) => c.type === "type_identifier")
        .map((c) => c.text);
      const implName = typeIds.length >= 2
        ? `${typeIds[0]} for ${typeIds[1]}`
        : (typeIds[0] ?? "impl");
      const declList = child.children.find((c) => c.type === "declaration_list");
      if (declList) {
        for (const member of declList.children) {
          if (member.type === "function_item") {
            const methodName = member.childForFieldName("name")?.text;
            if (methodName) {
              boundaries.push(nodeBoundary(member, "method", `${implName}.${methodName}`));
            }
          }
        }
      }
    }
  }
  return boundaries;
}

/** Kotlin: function_declaration, class_declaration + method children. */
function walkKotlin(root: SyntaxNode): Boundary[] {
  const boundaries: Boundary[] = [];
  for (const child of root.children) {
    if (child.type === "function_declaration") {
      const nameNode = child.children.find((c) => c.type === "simple_identifier");
      if (nameNode?.text) boundaries.push(nodeBoundary(child, "function", nameNode.text));
    } else if (child.type === "class_declaration") {
      const nameNode = child.children.find((c) => c.type === "type_identifier");
      if (nameNode?.text) {
        const name = nameNode.text;
        boundaries.push(nodeBoundary(child, "class", name));
        const body = child.children.find((c) => c.type === "class_body");
        if (body) {
          for (const member of body.children) {
            if (member.type === "function_declaration") {
              const methodName = member.children.find((c) => c.type === "simple_identifier")?.text;
              if (methodName) {
                boundaries.push(nodeBoundary(member, "method", `${name}.${methodName}`));
              }
            }
          }
        }
      }
    }
  }
  return boundaries;
}

/** Ruby: method, singleton_method, class, module. */
function walkRuby(root: SyntaxNode): Boundary[] {
  const boundaries: Boundary[] = [];
  for (const child of root.children) {
    if (child.type === "method" || child.type === "singleton_method") {
      const name = child.childForFieldName("name")?.text;
      if (name) boundaries.push(nodeBoundary(child, "function", name));
    } else if (child.type === "class" || child.type === "module") {
      const name = child.childForFieldName("name")?.text;
      if (name) boundaries.push(nodeBoundary(child, "class", name));
    }
  }
  return boundaries;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

/** Build a Boundary from an AST node (converts 0-based rows to 1-based lines). */
function nodeBoundary(node: SyntaxNode, kind: Boundary["kind"], name: string): Boundary {
  return {
    kind,
    name,
    startLine: node.startPosition.row + 1,
    endLine: node.endPosition.row + 1,
  };
}

/** Single "file" fallback chunk covering the whole source. */
function makeFileChunk(filePath: string, source: string): CodeChunk {
  const lineCount = source ? source.split("\n").length : 1;
  return {
    filePath,
    id: filePath,
    kind: "file",
    name: filePath,
    startLine: 1,
    endLine: lineCount,
    content: source,
  };
}

/**
 * Split an oversized chunk on blank lines, keeping each piece ≤ maxChunkChars.
 * Piece IDs are suffixed with a 1-based part index: "MyClass:1", "MyClass:2".
 */
function splitOnBlankLines(
  filePath: string,
  baseName: string,
  kind: Boundary["kind"],
  lines: string[],
  firstLine: number,
  maxChunkChars: number,
): CodeChunk[] {
  const chunks: CodeChunk[] = [];
  let currentLines: string[] = [];
  let currentStart = firstLine;
  let partIndex = 1;

  const flush = (endLine: number) => {
    if (currentLines.length === 0) return;
    chunks.push({
      filePath,
      id: `${baseName}:${partIndex}`,
      kind,
      name: baseName,
      startLine: currentStart,
      endLine,
      content: currentLines.join("\n"),
    });
    partIndex++;
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]!;
    currentLines.push(line);
    const currentContent = currentLines.join("\n");

    if (
      line.trim() === "" &&
      currentContent.length > maxChunkChars &&
      currentLines.length > 1
    ) {
      flush(firstLine + i);
      currentStart = firstLine + i + 1;
      currentLines = [];
    }
  }

  if (currentLines.length > 0) {
    flush(firstLine + lines.length - 1);
  }

  return chunks;
}

