/**
 * src/reporting/transcript.ts — Session transcript saving (FR-015)
 *
 * Saves Pi session messages as newline-delimited JSON (JSONL) to
 * the run artifacts directory: `{outputDir}/session-{sessionName}.jsonl`
 *
 * Implementation task: T063
 */

import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";

/**
 * Save a session transcript to disk in JSONL format.
 *
 * Each entry in `messages` is serialised as a single JSON line. An empty
 * messages array produces an empty file. The `outputDir` is created
 * recursively if it does not already exist.
 *
 * @param sessionName - Logical session name (e.g. "context", "plan", "implement").
 *                      Produces filename `session-{sessionName}.jsonl`.
 * @param messages    - Array of message/event objects from the Pi SDK session.
 * @param outputDir   - Directory to write the file into (created if absent).
 * @returns           - Absolute path to the written JSONL file.
 */
export async function saveTranscript(
  sessionName: string,
  messages: unknown[],
  outputDir: string,
): Promise<string> {
  await mkdir(outputDir, { recursive: true });

  const content = messages.map((m) => JSON.stringify(m)).join("\n");
  const filePath = join(outputDir, `session-${sessionName}.jsonl`);
  await writeFile(filePath, content, "utf-8");

  return filePath;
}
