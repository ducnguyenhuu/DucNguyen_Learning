/**
 * tests/unit/context/embeddings.test.ts — T037 / T044
 *
 * Tests for the EmbeddingsIndex class:
 *  - constructor: stores options, creates LocalIndex
 *  - index(): generates embeddings + upserts via vectra batch
 *  - query(): embeds query + maps QueryResult → EmbeddingSearchResult
 *  - save() / load(): persistence helpers
 *
 * @xenova/transformers and vectra are fully mocked — no model downloads or disk I/O.
 */

import { describe, it, expect, beforeEach, vi } from "vitest";

// ─── @xenova/transformers mock ────────────────────────────────────────────────

const { mockPipeline, mockExtractor } = vi.hoisted(() => {
  const mockExtractor = vi.fn();
  const mockPipeline = vi.fn().mockResolvedValue(mockExtractor);
  return { mockPipeline, mockExtractor };
});

vi.mock("@xenova/transformers", () => ({ pipeline: mockPipeline }));

// ─── vectra mock ──────────────────────────────────────────────────────────────

const {
  mockIsIndexCreated,
  mockCreateIndex,
  mockBeginUpdate,
  mockUpsertItem,
  mockEndUpdate,
  mockCancelUpdate,
  mockQueryItems,
  MockLocalIndex,
} = vi.hoisted(() => {
  const mockIsIndexCreated = vi.fn().mockResolvedValue(true);
  const mockCreateIndex = vi.fn().mockResolvedValue(undefined);
  const mockBeginUpdate = vi.fn().mockResolvedValue(undefined);
  const mockUpsertItem = vi.fn().mockResolvedValue({});
  const mockEndUpdate = vi.fn().mockResolvedValue(undefined);
  const mockCancelUpdate = vi.fn();
  const mockQueryItems = vi.fn().mockResolvedValue([]);
  const MockLocalIndex = vi.fn().mockImplementation(() => ({
    isIndexCreated: mockIsIndexCreated,
    createIndex: mockCreateIndex,
    beginUpdate: mockBeginUpdate,
    upsertItem: mockUpsertItem,
    endUpdate: mockEndUpdate,
    cancelUpdate: mockCancelUpdate,
    queryItems: mockQueryItems,
  }));
  return {
    mockIsIndexCreated,
    mockCreateIndex,
    mockBeginUpdate,
    mockUpsertItem,
    mockEndUpdate,
    mockCancelUpdate,
    mockQueryItems,
    MockLocalIndex,
  };
});

vi.mock("vectra", () => ({ LocalIndex: MockLocalIndex }));

// ─── System under test ────────────────────────────────────────────────────────

import {
  EmbeddingsIndex,
  type EmbeddingsOptions,
  type EmbeddingSearchResult,
} from "../../../src/context/embeddings.js";
import type { CodeChunk } from "../../../src/context/chunker.js";

// ─── Helpers ──────────────────────────────────────────────────────────────────

const FAKE_VECTOR = new Float32Array(384).fill(0.1);

function makeChunk(name: string, content = "function body"): CodeChunk {
  return {
    filePath: `src/${name}.ts`,
    id: name,
    kind: "function",
    name,
    startLine: 1,
    endLine: 10,
    content,
  };
}

const BASE_OPTIONS: EmbeddingsOptions = {
  indexPath: "/tmp/test-index",
  model: "Xenova/all-MiniLM-L6-v2",
};

beforeEach(() => {
  vi.clearAllMocks();
  // Default: extractor returns a tensor-like object
  mockExtractor.mockResolvedValue({ data: FAKE_VECTOR });
  // Default: index already exists
  mockIsIndexCreated.mockResolvedValue(true);
});

// ─── Constructor ─────────────────────────────────────────────────────────────

describe("EmbeddingsIndex — constructor", () => {
  it("creates a LocalIndex pointed at indexPath", () => {
    new EmbeddingsIndex(BASE_OPTIONS);
    expect(MockLocalIndex).toHaveBeenCalledWith(BASE_OPTIONS.indexPath);
  });

  it("does not call pipeline during construction (lazy init)", () => {
    new EmbeddingsIndex(BASE_OPTIONS);
    expect(mockPipeline).not.toHaveBeenCalled();
  });

  it("requires only indexPath — model is optional", () => {
    expect(() => new EmbeddingsIndex({ indexPath: "/some/path" })).not.toThrow();
  });
});

// ─── index() ─────────────────────────────────────────────────────────────────

describe("EmbeddingsIndex.index()", () => {
  it("is a no-op for empty chunk array", async () => {
    const idx = new EmbeddingsIndex(BASE_OPTIONS);
    await idx.index([]);
    expect(mockBeginUpdate).not.toHaveBeenCalled();
    expect(mockExtractor).not.toHaveBeenCalled();
  });

  it("calls pipeline once (lazy init) then reuses it", async () => {
    const idx = new EmbeddingsIndex(BASE_OPTIONS);
    await idx.index([makeChunk("a"), makeChunk("b")]);
    expect(mockPipeline).toHaveBeenCalledTimes(1);
    expect(mockPipeline).toHaveBeenCalledWith("feature-extraction", "Xenova/all-MiniLM-L6-v2");
  });

  it("uses default model when none provided", async () => {
    const idx = new EmbeddingsIndex({ indexPath: "/tmp/x" });
    await idx.index([makeChunk("a")]);
    expect(mockPipeline).toHaveBeenCalledWith(
      "feature-extraction",
      "Xenova/all-MiniLM-L6-v2",
    );
  });

  it("calls extractor for each chunk with mean pooling and normalize", async () => {
    const idx = new EmbeddingsIndex(BASE_OPTIONS);
    await idx.index([makeChunk("a"), makeChunk("b")]);
    expect(mockExtractor).toHaveBeenCalledTimes(2);
    expect(mockExtractor).toHaveBeenCalledWith(expect.any(String), {
      pooling: "mean",
      normalize: true,
    });
  });

  it("creates the index when it does not exist", async () => {
    mockIsIndexCreated.mockResolvedValue(false);
    const idx = new EmbeddingsIndex(BASE_OPTIONS);
    await idx.index([makeChunk("fn")]);
    expect(mockCreateIndex).toHaveBeenCalledWith({ version: 1 });
  });

  it("skips createIndex when index already exists", async () => {
    mockIsIndexCreated.mockResolvedValue(true);
    const idx = new EmbeddingsIndex(BASE_OPTIONS);
    await idx.index([makeChunk("fn")]);
    expect(mockCreateIndex).not.toHaveBeenCalled();
  });

  it("wraps upserts in beginUpdate / endUpdate batch", async () => {
    const idx = new EmbeddingsIndex(BASE_OPTIONS);
    await idx.index([makeChunk("fn")]);
    expect(mockBeginUpdate).toHaveBeenCalledTimes(1);
    expect(mockEndUpdate).toHaveBeenCalledTimes(1);
  });

  it("upserts each chunk with the embedding vector and metadata", async () => {
    const chunk = makeChunk("validateEmail", "function validateEmail() {}");
    const idx = new EmbeddingsIndex(BASE_OPTIONS);
    await idx.index([chunk]);

    expect(mockUpsertItem).toHaveBeenCalledTimes(1);
    const call = mockUpsertItem.mock.calls[0]![0] as {
      id: string;
      metadata: Record<string, unknown>;
      vector: number[];
    };
    expect(call.id).toBe("validateEmail");
    expect(call.metadata.filePath).toBe("src/validateEmail.ts");
    expect(call.metadata.content).toBe("function validateEmail() {}");
    expect(Array.isArray(call.vector)).toBe(true);
    expect(call.vector.length).toBe(384);
  });

  it("calls cancelUpdate when upsert throws", async () => {
    mockUpsertItem.mockRejectedValueOnce(new Error("disk full"));
    const idx = new EmbeddingsIndex(BASE_OPTIONS);
    await expect(idx.index([makeChunk("fn")])).rejects.toThrow("disk full");
    expect(mockCancelUpdate).toHaveBeenCalledTimes(1);
    expect(mockEndUpdate).not.toHaveBeenCalled();
  });
});

// ─── query() ─────────────────────────────────────────────────────────────────

describe("EmbeddingsIndex.query()", () => {
  it("returns empty array when index has no matching items", async () => {
    mockQueryItems.mockResolvedValue([]);
    const idx = new EmbeddingsIndex(BASE_OPTIONS);
    const results = await idx.query("email validation");
    expect(results).toEqual([]);
  });

  it("embeds the query text and passes vector + topK to queryItems", async () => {
    mockQueryItems.mockResolvedValue([]);
    const idx = new EmbeddingsIndex(BASE_OPTIONS);
    await idx.query("email validation", 3);
    expect(mockExtractor).toHaveBeenCalledWith("email validation", {
      pooling: "mean",
      normalize: true,
    });
    expect(mockQueryItems).toHaveBeenCalledWith(
      expect.arrayContaining([expect.any(Number)]),
      3,
    );
  });

  it("defaults topK to 5", async () => {
    mockQueryItems.mockResolvedValue([]);
    const idx = new EmbeddingsIndex(BASE_OPTIONS);
    await idx.query("something");
    expect(mockQueryItems).toHaveBeenCalledWith(expect.any(Array), 5);
  });

  it("maps QueryResult items back to EmbeddingSearchResult", async () => {
    const chunk = makeChunk("hashPassword", "function hashPassword() {}");
    mockQueryItems.mockResolvedValue([
      {
        item: {
          id: chunk.id,
          vector: Array.from(FAKE_VECTOR),
          norm: 1,
          metadata: {
            filePath: chunk.filePath,
            id: chunk.id,
            kind: chunk.kind,
            name: chunk.name,
            startLine: chunk.startLine,
            endLine: chunk.endLine,
            content: chunk.content,
          },
        },
        score: 0.91,
      },
    ]);

    const idx = new EmbeddingsIndex(BASE_OPTIONS);
    const results = await idx.query("password hashing", 1);

    expect(results).toHaveLength(1);
    expect(results[0]).toMatchObject<Partial<EmbeddingSearchResult>>({
      score: 0.91,
      chunk: expect.objectContaining({
        id: "hashPassword",
        name: "hashPassword",
        filePath: "src/hashPassword.ts",
        content: "function hashPassword() {}",
      }),
    });
  });

  it("returns results sorted by descending score (vectra's responsibility — test pass-through)", async () => {
    mockQueryItems.mockResolvedValue([
      {
        item: { id: "a", vector: [], norm: 1, metadata: { filePath: "src/a.ts", id: "a", kind: "function", name: "a", startLine: 1, endLine: 1, content: "" } },
        score: 0.95,
      },
      {
        item: { id: "b", vector: [], norm: 1, metadata: { filePath: "src/b.ts", id: "b", kind: "function", name: "b", startLine: 1, endLine: 1, content: "" } },
        score: 0.80,
      },
    ]);
    const idx = new EmbeddingsIndex(BASE_OPTIONS);
    const results = await idx.query("anything", 2);
    expect(results[0]?.score).toBe(0.95);
    expect(results[1]?.score).toBe(0.80);
  });
});

// ─── save() ──────────────────────────────────────────────────────────────────

describe("EmbeddingsIndex.save()", () => {
  it("resolves without error (no-op — vectra persists in index())", async () => {
    const idx = new EmbeddingsIndex(BASE_OPTIONS);
    await expect(idx.save()).resolves.toBeUndefined();
  });
});

// ─── load() ──────────────────────────────────────────────────────────────────

describe("EmbeddingsIndex.load()", () => {
  it("returns true when a persisted index exists", async () => {
    mockIsIndexCreated.mockResolvedValue(true);
    const idx = new EmbeddingsIndex(BASE_OPTIONS);
    expect(await idx.load()).toBe(true);
  });

  it("returns false when no index exists on disk", async () => {
    mockIsIndexCreated.mockResolvedValue(false);
    const idx = new EmbeddingsIndex(BASE_OPTIONS);
    expect(await idx.load()).toBe(false);
  });
});

// ─── EmbeddingSearchResult interface contract ─────────────────────────────────

describe("EmbeddingSearchResult — interface contract", () => {
  it("contract: result has a chunk and a score [0,1]", () => {
    const result: EmbeddingSearchResult = {
      chunk: makeChunk("validateEmail", "function validateEmail(email: string) {}"),
      score: 0.87,
    };
    expect(result.score).toBeGreaterThanOrEqual(0);
    expect(result.score).toBeLessThanOrEqual(1);
    expect(result.chunk).toBeDefined();
    expect(typeof result.chunk.content).toBe("string");
  });

  it("contract: score is a finite number", () => {
    const result: EmbeddingSearchResult = {
      chunk: makeChunk("foo", ""),
      score: 0.5,
    };
    expect(Number.isFinite(result.score)).toBe(true);
  });
});

// ─── EmbeddingsOptions interface contract ─────────────────────────────────────

describe("EmbeddingsOptions — interface contract", () => {
  it("contract: indexPath is required", () => {
    const opts: EmbeddingsOptions = { indexPath: "/data/idx" };
    expect(typeof opts.indexPath).toBe("string");
  });

  it("contract: model is optional", () => {
    const opts: EmbeddingsOptions = { indexPath: "/data/idx" };
    expect(opts.model).toBeUndefined();
  });
});
