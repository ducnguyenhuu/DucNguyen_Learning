/**
 * src/context/embeddings.ts — Embedding indexing with vectra + @xenova/transformers (US2, T044)
 *
 * Indexes code chunks into a vectra LocalIndex and supports cosine-similarity
 * queries. Research Decision R2: vectra (pure TS, file-based) + @xenova/transformers
 * (local ONNX model, no external API required).
 *
 * Usage:
 *   const idx = new EmbeddingsIndex({ indexPath: "/tmp/idx" });
 *   await idx.index(chunks);             // generate embeddings + persist
 *   const results = await idx.query("email validation", 5);
 */

import { pipeline } from "@xenova/transformers";
import { LocalIndex } from "vectra";
import type { CodeChunk } from "./chunker.js";

// ─── Types ────────────────────────────────────────────────────────────────────

export interface EmbeddingSearchResult {
  chunk: CodeChunk;
  /** Cosine similarity score [0, 1] */
  score: number;
}

// ─── Options ──────────────────────────────────────────────────────────────────

export interface EmbeddingsOptions {
  /** Directory where the vectra index files are stored. */
  indexPath: string;
  /** Local model name — passed to @xenova/transformers. Default: "Xenova/all-MiniLM-L6-v2" */
  model?: string;
}

// ─── Internal metadata stored per vector ─────────────────────────────────────

interface ChunkMetadata {
  filePath: string;
  id: string;
  kind: string;
  name: string;
  startLine: number;
  endLine: number;
  content: string;
  [key: string]: string | number | boolean;
}

// ─── EmbeddingsIndex ──────────────────────────────────────────────────────────

const DEFAULT_MODEL = "Xenova/all-MiniLM-L6-v2";

/**
 * Manages a vectra-backed semantic index of code chunks.
 *
 * - `index(chunks)` — generates embeddings for each chunk and upserts into the
 *   vectra LocalIndex as a single batched write (one disk flush).
 * - `query(text, topK)` — embeds the query text and returns the top-k most
 *   similar chunks with their cosine-similarity scores.
 * - `save()` — explicit flush (no-op: vectra already persists in `index()`).
 * - `load()` — returns true if a persisted index exists on disk.
 */
export class EmbeddingsIndex {
  private readonly _options: EmbeddingsOptions;
  private readonly _localIndex: LocalIndex<ChunkMetadata>;
  private _extractor: Awaited<ReturnType<typeof pipeline>> | null = null;

  constructor(options: EmbeddingsOptions) {
    this._options = options;
    this._localIndex = new LocalIndex<ChunkMetadata>(options.indexPath);
  }

  // ── Public API ───────────────────────────────────────────────────────────

  /**
   * Add a list of code chunks to the index, generating embeddings for each.
   * Uses a single vectra batch (beginUpdate / endUpdate) for efficiency.
   * Creates the index on disk if it does not already exist.
   */
  async index(chunks: CodeChunk[]): Promise<void> {
    if (chunks.length === 0) return;

    if (!(await this._localIndex.isIndexCreated())) {
      await this._localIndex.createIndex({ version: 1 });
    }

    await this._localIndex.beginUpdate();
    try {
      for (const chunk of chunks) {
        const vector = await this._embed(chunk.content);
        const metadata: ChunkMetadata = {
          filePath: chunk.filePath,
          id: chunk.id,
          kind: chunk.kind,
          name: chunk.name,
          startLine: chunk.startLine,
          endLine: chunk.endLine,
          content: chunk.content,
        };
        await this._localIndex.upsertItem({ id: chunk.id, metadata, vector });
      }
      await this._localIndex.endUpdate();
    } catch (err) {
      this._localIndex.cancelUpdate();
      throw err;
    }
  }

  /**
   * Query the index for the most similar chunks to the given text.
   * Returns up to `topK` results sorted by descending similarity score.
   */
  async query(text: string, topK = 5): Promise<EmbeddingSearchResult[]> {
    const vector = await this._embed(text);
    const results = await this._localIndex.queryItems<ChunkMetadata>(vector, topK);
    return results.map(({ item, score }) => ({
      chunk: {
        filePath: item.metadata.filePath,
        id: item.metadata.id,
        kind: item.metadata.kind as CodeChunk["kind"],
        name: item.metadata.name,
        startLine: item.metadata.startLine,
        endLine: item.metadata.endLine,
        content: item.metadata.content,
      } satisfies CodeChunk,
      score,
    }));
  }

  /**
   * Persist the index to disk.
   * vectra already flushes each batch in `index()`, so this is a semantic
   * no-op that exists for explicit-flush call sites.
   */
  async save(): Promise<void> {
    // no-op — vectra persists inside index() via beginUpdate/endUpdate
  }

  /**
   * Returns true if a saved index already exists at `indexPath`.
   * Use this to decide whether to re-index or reuse an existing index.
   */
  async load(): Promise<boolean> {
    return this._localIndex.isIndexCreated();
  }

  // ── Private helpers ──────────────────────────────────────────────────────

  /** Lazy-initialise the @xenova/transformers feature-extraction pipeline. */
  private async _ensurePipeline(): Promise<Awaited<ReturnType<typeof pipeline>>> {
    if (this._extractor === null) {
      const model = this._options.model ?? DEFAULT_MODEL;
      this._extractor = await pipeline("feature-extraction", model);
    }
    return this._extractor;
  }

  /**
   * Generate a normalised embedding vector for `text`.
   * Uses mean pooling + L2 normalisation (standard for sentence-transformers).
   */
  private async _embed(text: string): Promise<number[]> {
    const extractor = await this._ensurePipeline();
    // @xenova/transformers returns a Tensor; we use mean pooling + normalize
    const output = await (extractor as (t: string, opts: Record<string, unknown>) => Promise<{ data: Float32Array }>)(
      text,
      { pooling: "mean", normalize: true },
    );
    return Array.from(output.data);
  }
}
