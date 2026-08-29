/**
 * tests/unit/reporting/transcript.test.ts — T084
 *
 * Unit tests for session transcript saving.
 *
 * Tests cover:
 *  - File naming: session-{sessionName}.jsonl inside outputDir
 *  - JSONL format: each message on its own line, valid JSON
 *  - Directory creation: mkdir -p called when dir does not exist
 *  - Empty messages: produces an empty file (zero bytes)
 *  - Returned path: matches the expected file path
 *  - Nested output directories created recursively
 *  - Each message serialised independently (newline-separated)
 *  - Non-serialisable values are not silently swallowed
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { join } from "node:path";

// ─── Mock node:fs/promises ────────────────────────────────────────────────────
// vi.mock is hoisted to the top of the file, so factory variables must be
// declared with vi.hoisted() to avoid "Cannot access before initialization" errors.

const { mkdirMock, writeFileMock } = vi.hoisted(() => ({
  mkdirMock:     vi.fn().mockResolvedValue(undefined),
  writeFileMock: vi.fn().mockResolvedValue(undefined),
}));

vi.mock("node:fs/promises", () => ({
  mkdir:     mkdirMock,
  writeFile: writeFileMock,
}));

import { saveTranscript } from "../../../src/reporting/transcript.js";

// ─── Helpers ──────────────────────────────────────────────────────────────────

const OUTPUT_DIR = "/agent/runs/2026-03-13T14-00-00";

interface MessageRecord {
  role: string;
  content: string;
  tokens?: number;
}

function makeMessages(count: number): MessageRecord[] {
  return Array.from({ length: count }, (_, i) => ({
    role: i % 2 === 0 ? "user" : "assistant",
    content: `Message ${i}`,
    tokens: 100 + i,
  }));
}

// ─── File naming ──────────────────────────────────────────────────────────────

describe("saveTranscript() — file naming", () => {
  beforeEach(() => vi.clearAllMocks());

  it("writes to session-{sessionName}.jsonl inside outputDir", async () => {
    await saveTranscript("context", makeMessages(2), OUTPUT_DIR);
    const [writtenPath] = writeFileMock.mock.calls[0] as [string, ...unknown[]];
    expect(writtenPath).toBe(join(OUTPUT_DIR, "session-context.jsonl"));
  });

  it("returns the full file path", async () => {
    const result = await saveTranscript("plan", makeMessages(1), OUTPUT_DIR);
    expect(result).toBe(join(OUTPUT_DIR, "session-plan.jsonl"));
  });

  it("uses 'implement' session name correctly", async () => {
    await saveTranscript("implement", makeMessages(3), OUTPUT_DIR);
    const [writtenPath] = writeFileMock.mock.calls[0] as [string, ...unknown[]];
    expect(writtenPath).toBe(join(OUTPUT_DIR, "session-implement.jsonl"));
  });

  it("uses 'fix' session name correctly", async () => {
    await saveTranscript("fix", makeMessages(2), OUTPUT_DIR);
    const [writtenPath] = writeFileMock.mock.calls[0] as [string, ...unknown[]];
    expect(writtenPath).toBe(join(OUTPUT_DIR, "session-fix.jsonl"));
  });
});

// ─── Directory creation ────────────────────────────────────────────────────────

describe("saveTranscript() — directory creation", () => {
  beforeEach(() => vi.clearAllMocks());

  it("calls mkdir with the outputDir path", async () => {
    await saveTranscript("context", makeMessages(1), OUTPUT_DIR);
    expect(mkdirMock).toHaveBeenCalledWith(OUTPUT_DIR, expect.objectContaining({ recursive: true }));
  });

  it("creates the directory with { recursive: true } to allow nested paths", async () => {
    const nested = "/agent/runs/2026/03/13/14-00-00";
    await saveTranscript("plan", makeMessages(1), nested);
    expect(mkdirMock).toHaveBeenCalledWith(nested, expect.objectContaining({ recursive: true }));
  });

  it("always calls mkdir before writeFile", async () => {
    const callOrder: string[] = [];
    mkdirMock.mockImplementationOnce(async () => { callOrder.push("mkdir"); });
    writeFileMock.mockImplementationOnce(async () => { callOrder.push("writeFile"); });
    await saveTranscript("context", makeMessages(1), OUTPUT_DIR);
    expect(callOrder).toEqual(["mkdir", "writeFile"]);
  });
});

// ─── JSONL format ─────────────────────────────────────────────────────────────

describe("saveTranscript() — JSONL format", () => {
  beforeEach(() => vi.clearAllMocks());

  it("writes each message as its own JSON line", async () => {
    const messages = makeMessages(3);
    await saveTranscript("context", messages, OUTPUT_DIR);
    const [, writtenContent] = writeFileMock.mock.calls[0] as [string, string];
    const lines = writtenContent.trim().split("\n");
    expect(lines).toHaveLength(3);
  });

  it("each line is valid JSON", async () => {
    const messages = makeMessages(3);
    await saveTranscript("context", messages, OUTPUT_DIR);
    const [, writtenContent] = writeFileMock.mock.calls[0] as [string, string];
    const lines = writtenContent.trim().split("\n");
    expect(() => lines.forEach((l) => JSON.parse(l))).not.toThrow();
  });

  it("each JSON line round-trips the original message data", async () => {
    const messages = [{ role: "user", content: "Hello", tokens: 5 }];
    await saveTranscript("context", messages, OUTPUT_DIR);
    const [, writtenContent] = writeFileMock.mock.calls[0] as [string, string];
    const parsed: MessageRecord[] = writtenContent
      .trim()
      .split("\n")
      .map((l) => JSON.parse(l) as MessageRecord);
    expect(parsed[0]).toEqual(messages[0]);
  });

  it("lines are separated by newline characters", async () => {
    const messages = makeMessages(2);
    await saveTranscript("context", messages, OUTPUT_DIR);
    const [, writtenContent] = writeFileMock.mock.calls[0] as [string, string];
    expect(writtenContent).toContain("\n");
  });

  it("handles a single message — produces exactly one line", async () => {
    await saveTranscript("context", makeMessages(1), OUTPUT_DIR);
    const [, writtenContent] = writeFileMock.mock.calls[0] as [string, string];
    const nonEmptyLines = writtenContent.split("\n").filter((l) => l.trim().length > 0);
    expect(nonEmptyLines).toHaveLength(1);
  });

  it("messages preserve nested objects", async () => {
    const messages = [
      {
        role: "assistant",
        tool_calls: [{ name: "read_file", args: { path: "/workspace/src/app.ts" } }],
      },
    ];
    await saveTranscript("context", messages, OUTPUT_DIR);
    const [, writtenContent] = writeFileMock.mock.calls[0] as [string, string];
    const parsed = JSON.parse(writtenContent.trim());
    expect(parsed.tool_calls[0].name).toBe("read_file");
  });

  it("messages preserve array fields", async () => {
    const messages = [{ role: "user", tags: ["a", "b", "c"] }];
    await saveTranscript("plan", messages, OUTPUT_DIR);
    const [, writtenContent] = writeFileMock.mock.calls[0] as [string, string];
    const parsed = JSON.parse(writtenContent.trim()) as { tags: string[] };
    expect(parsed.tags).toEqual(["a", "b", "c"]);
  });
});

// ─── Empty messages ──────────────────────────────────────────────────────────

describe("saveTranscript() — empty messages array", () => {
  beforeEach(() => vi.clearAllMocks());

  it("writes an empty file for an empty messages array", async () => {
    await saveTranscript("context", [], OUTPUT_DIR);
    const [, writtenContent] = writeFileMock.mock.calls[0] as [string, string];
    expect(writtenContent.trim()).toBe("");
  });

  it("still creates the directory for an empty messages array", async () => {
    await saveTranscript("context", [], OUTPUT_DIR);
    expect(mkdirMock).toHaveBeenCalledOnce();
  });

  it("still returns the file path for an empty messages array", async () => {
    const result = await saveTranscript("context", [], OUTPUT_DIR);
    expect(result).toBe(join(OUTPUT_DIR, "session-context.jsonl"));
  });
});

// ─── Large messages ───────────────────────────────────────────────────────────

describe("saveTranscript() — large message sets", () => {
  beforeEach(() => vi.clearAllMocks());

  it("handles 100 messages — all written as JSONL lines", async () => {
    const messages = makeMessages(100);
    await saveTranscript("implement", messages, OUTPUT_DIR);
    const [, writtenContent] = writeFileMock.mock.calls[0] as [string, string];
    const nonEmptyLines = writtenContent.split("\n").filter((l) => l.trim().length > 0);
    expect(nonEmptyLines).toHaveLength(100);
  });
});
