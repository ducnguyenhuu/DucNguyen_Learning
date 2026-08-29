/**
 * src/context/dep-graph.ts — Dependency graph builder (US2, T043)
 *
 * Parses import/require/from statements in source files to build a directed
 * dependency graph. Supports finding which files import a given file
 * (importers) and which files a given file depends on (importees).
 *
 * Uses regex-based extraction of import specifiers from source text — no
 * WASM or tree-sitter required — then resolves relative specifiers to
 * workspace-relative file paths using the same path conventions as the other
 * context modules.
 */

import { readFile } from "node:fs/promises";
import { join, dirname, extname, normalize } from "node:path";

// ─── Types ────────────────────────────────────────────────────────────────────

/** A directed edge A → B meaning file A imports from file B. */
export interface ImportEdge {
  /** Importer: the file that contains the import statement */
  from: string;
  /** Importee: the resolved module that is imported */
  to: string;
  /** The raw import specifier as written in source code */
  specifier: string;
}

export interface DependencyGraph {
  /** All resolved edges */
  edges: ImportEdge[];
}

// ─── Options ──────────────────────────────────────────────────────────────────

export interface DepGraphOptions {
  /** Absolute workspace root — used for resolving relative imports */
  workspacePath: string;
  /** File extensions to include. Default: [".ts", ".tsx", ".js", ".jsx", ".mts", ".mjs", ".cts", ".cjs"] */
  extensions?: string[];
}

// ─── buildDepGraph ────────────────────────────────────────────────────────────

const DEFAULT_EXTENSIONS = [".ts", ".tsx", ".js", ".jsx", ".mts", ".mjs", ".cts", ".cjs"];

/**
 * Walk `filePaths`, read each file, parse all import/export/require/dynamic-
 * import specifiers, resolve relative specifiers to workspace-relative paths,
 * and return the resulting dependency graph.
 *
 * - External (non-relative) specifiers are ignored.
 * - Files that cannot be read are silently skipped.
 * - Specifier resolution prefers exact matches in `filePaths`, then tries
 *   adding each extension, then index files, then falls back to an inferred path.
 */
export async function buildDepGraph(
  filePaths: string[],
  options: DepGraphOptions,
): Promise<DependencyGraph> {
  const { workspacePath } = options;
  const extensions = options.extensions ?? DEFAULT_EXTENSIONS;
  const edges: ImportEdge[] = [];

  for (const filePath of filePaths) {
    const absPath = join(workspacePath, filePath);
    let source: string;
    try {
      source = await readFile(absPath, "utf-8");
    } catch {
      continue; // unreadable — skip
    }

    for (const specifier of extractSpecifiers(source)) {
      if (!specifier.startsWith(".")) continue; // skip external/node modules
      const to = resolveSpecifier(filePath, specifier, filePaths, extensions);
      edges.push({ from: filePath, to, specifier });
    }
  }

  return { edges };
}

// ─── Private helpers ──────────────────────────────────────────────────────────

/**
 * Extract all import specifiers from `source` using four regex passes:
 *  1. `from "specifier"` — static import/export … from
 *  2. `import "specifier"` — side-effect imports (no bindings)
 *  3. `require("specifier")` — CommonJS
 *  4. `import("specifier")` — dynamic imports
 *
 * Duplicates are removed. False positives from comments/strings are rare
 * enough and harmless enough for this use-case.
 */
function extractSpecifiers(source: string): string[] {
  const set = new Set<string>();

  // import … from "x" / export … from "x"
  for (const m of source.matchAll(/\bfrom\s+['"]([^'"]+)['"]/gm)) set.add(m[1]!);

  // import "x" — side-effect (line must start with import, not `from import`)
  for (const m of source.matchAll(/^[ \t]*import\s+['"]([^'"]+)['"]/gm)) set.add(m[1]!);

  // require("x")
  for (const m of source.matchAll(/\brequire\s*\(\s*['"]([^'"]+)['"]\s*\)/gm)) set.add(m[1]!);

  // import("x") — dynamic
  for (const m of source.matchAll(/\bimport\s*\(\s*['"]([^'"]+)['"]\s*\)/gm)) set.add(m[1]!);

  return [...set];
}

/**
 * Resolve a relative specifier from `fromFile` to a workspace-relative path.
 *
 * Resolution order:
 *  1. Exact match in `filePaths` (specifier already has extension)
 *  2. `base + ext` for each extension in order
 *  3. `base/index<ext>` for each extension (directory imports)
 *  4. Fallback: `base` + extension inferred from the source file
 */
function resolveSpecifier(
  fromFile: string,
  specifier: string,
  filePaths: string[],
  extensions: string[],
): string {
  const base = normalize(join(dirname(fromFile), specifier));

  if (filePaths.includes(base)) return base;

  for (const ext of extensions) {
    const candidate = base + ext;
    if (filePaths.includes(candidate)) return candidate;
  }

  for (const ext of extensions) {
    const candidate = join(base, `index${ext}`);
    if (filePaths.includes(candidate)) return candidate;
  }

  // Fall back to the source file's own extension (or .ts for unknown)
  const inferredExt = extname(fromFile) || ".ts";
  return base + inferredExt;
}

// ─── Query helpers ─────────────────────────────────────────────────────────────

/**
 * Return the list of files that import `filePath` (direct importers only).
 */
export function getImporters(graph: DependencyGraph, filePath: string): string[] {
  return graph.edges.filter((e) => e.to === filePath).map((e) => e.from);
}

/**
 * Return the list of files that `filePath` imports (direct importees only).
 */
export function getImportees(graph: DependencyGraph, filePath: string): string[] {
  return graph.edges.filter((e) => e.from === filePath).map((e) => e.to);
}
