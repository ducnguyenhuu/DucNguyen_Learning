#!/usr/bin/env node
/**
 * scripts/warm-cache.ts — Pre-warm implementation (T047)
 *
 * Invoked by warm-cache.sh. Performs two operations:
 *  1. Build (or rebuild) the vectra embeddings index for semantic_search
 *  2. Generate and print a repo map summary for verification
 *
 * Run via warm-cache.sh — not intended to be called directly.
 */

import { parseArgs } from "node:util";
import { mkdir, readFile } from "node:fs/promises";
import { resolve, join } from "node:path";
import { generateRepoMap, formatRepoMap } from "../src/context/repo-map.js";
import { chunkFiles } from "../src/context/chunker.js";
import { EmbeddingsIndex } from "../src/context/embeddings.js";

// ─── CLI args ─────────────────────────────────────────────────────────────────

const { values } = parseArgs({
  options: {
    workspace: { type: "string" },
    index: { type: "string" },
  },
});

const workspacePath = resolve(values.workspace ?? process.cwd());
const indexPath = resolve(values.index ?? `${workspacePath}/.index`);
const embeddingModel = process.env["EMBEDDING_MODEL"] ?? "Xenova/all-MiniLM-L6-v2";
const repoMapMaxTokens = Number(process.env["REPO_MAP_TOKENS"] ?? 5_000);

// ─── Main ─────────────────────────────────────────────────────────────────────

async function main(): Promise<void> {
  // ── Step 1: Repo map ───────────────────────────────────────────────────────
  console.log("\n[1/3] Generating repo map...");
  const repoMap = await generateRepoMap({ workspacePath, maxTokens: repoMapMaxTokens });
  const repoMapText = formatRepoMap(repoMap);
  console.log(`      ${repoMap.files.length} files, ~${repoMap.tokenCount} tokens`);
  console.log(repoMapText);

  // ── Step 2: Chunk source files ─────────────────────────────────────────────
  console.log("[2/3] Chunking source files...");
  const fileInputs = await Promise.all(
    repoMap.files.map(async (f) => ({
      filePath: f.path,
      source: await readFile(join(workspacePath, f.path), "utf-8"),
    })),
  );
  const chunks = await chunkFiles(fileInputs);
  console.log(`      ${chunks.length} chunks extracted`);

  if (chunks.length === 0) {
    console.warn("      Warning: no chunks found — embedding index will be empty.");
  }

  // ── Step 3: Build embeddings index ────────────────────────────────────────
  console.log("[3/3] Building embeddings index...");
  console.log(`      model     : ${embeddingModel}`);
  console.log(`      index dir : ${indexPath}`);

  await mkdir(indexPath, { recursive: true });

  const embeddingsIndex = new EmbeddingsIndex({
    indexPath,
    model: embeddingModel,
  });

  const startMs = Date.now();
  await embeddingsIndex.index(chunks);
  const durationSec = ((Date.now() - startMs) / 1000).toFixed(1);

  console.log(`      ${chunks.length} chunks indexed in ${durationSec}s`);
  console.log("\n=== warm-cache: done ===");
}

main().catch((err) => {
  console.error("warm-cache failed:", err instanceof Error ? err.message : String(err));
  process.exit(1);
});
