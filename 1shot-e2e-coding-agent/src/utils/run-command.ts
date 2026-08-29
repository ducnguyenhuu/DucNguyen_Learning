/**
 * src/utils/run-command.ts — Shell command runner utility
 *
 * Wraps Node.js child_process.exec to run shell commands and return
 * stdout, stderr, and exit code without throwing on non-zero exit.
 */

import { exec } from "node:child_process";

export interface RunCommandResult {
  stdout: string;
  stderr: string;
  exitCode: number;
}

/**
 * Run a shell command in the given working directory.
 * Resolves with stdout, stderr, and exitCode.
 * Never rejects on non-zero exit — only rejects if the process cannot be spawned.
 */
export function runCommand(
  command: string,
  cwd: string,
): Promise<RunCommandResult> {
  return new Promise((resolve, reject) => {
    exec(command, { cwd }, (err, stdout, stderr) => {
      if (err && err.code === undefined) {
        // Process failed to spawn (e.g. command not found at OS level)
        reject(err);
        return;
      }
      resolve({
        stdout: stdout.trim(),
        stderr: stderr.trim(),
        exitCode: (err?.code as number | undefined) ?? 0,
      });
    });
  });
}
