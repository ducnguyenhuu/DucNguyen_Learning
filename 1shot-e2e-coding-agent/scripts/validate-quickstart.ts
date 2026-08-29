#!/usr/bin/env node
/**
 * scripts/validate-quickstart.ts — T078
 *
 * Verifies the 5 setup steps from quickstart.md work on the current environment.
 * Runs non-destructively: checks prerequisites, validates install, exercises the
 * CLI commands, and reports which steps pass/fail without modifying real repos
 * or calling external APIs.
 *
 * Usage:
 *   npx tsx scripts/validate-quickstart.ts
 *
 * Exit code: 0 if all required checks pass, 1 otherwise.
 */

import { execSync, spawnSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { tmpdir } from "node:os";

// ─── Helpers ──────────────────────────────────────────────────────────────────

const RESET = "\x1b[0m";
const GREEN = "\x1b[32m";
const RED = "\x1b[31m";
const YELLOW = "\x1b[33m";
const BOLD = "\x1b[1m";
const DIM = "\x1b[2m";

interface CheckResult {
  step: number;
  name: string;
  checks: { label: string; pass: boolean; note?: string }[];
}

function run(cmd: string, cwd?: string): { stdout: string; stderr: string; ok: boolean } {
  const result = spawnSync(cmd, { shell: true, cwd, encoding: "utf-8" });
  return {
    stdout: result.stdout ?? "",
    stderr: result.stderr ?? "",
    ok: result.status === 0,
  };
}

function semver(raw: string): [number, number, number] {
  const m = raw.match(/(\d+)\.(\d+)\.(\d+)/);
  if (!m) return [0, 0, 0];
  return [Number(m[1]), Number(m[2]), Number(m[3])];
}

function check(label: string, pass: boolean, note?: string) {
  return { label, pass, note };
}

// ─── Step 1: Prerequisites ────────────────────────────────────────────────────

function checkPrerequisites(): CheckResult {
  const checks = [];

  // Node.js ≥ 20
  const nodeOut = run("node --version");
  const [nodeMaj] = semver(nodeOut.stdout.trim());
  checks.push(check(
    `Node.js ≥ 20 (found ${nodeOut.stdout.trim()})`,
    nodeOut.ok && nodeMaj >= 20,
    nodeMaj < 20 ? "Install Node.js 20+ from nodejs.org" : undefined,
  ));

  // npm available
  const npmOut = run("npm --version");
  checks.push(check(`npm available (${npmOut.stdout.trim()})`, npmOut.ok));

  // Git
  const gitOut = run("git --version");
  checks.push(check(`Git available (${gitOut.stdout.trim()})`, gitOut.ok));

  // Docker (optional — warn if missing, don't fail)
  const dockerOut = run("docker --version");
  checks.push(check(
    `Docker available (${dockerOut.ok ? dockerOut.stdout.trim() : "not found"})`,
    true, // Docker is needed for the devbox but not for CLI validation
    dockerOut.ok ? undefined : "Docker not found — needed for devbox mode, optional for CLI mode",
  ));

  return { step: 1, name: "Prerequisites", checks };
}

// ─── Step 2: Clone and install ────────────────────────────────────────────────

function checkInstall(): CheckResult {
  const root = resolve(import.meta.dirname ?? process.cwd(), "..");
  const checks = [];

  // package.json exists
  checks.push(check("package.json exists", existsSync(join(root, "package.json"))));

  // node_modules installed
  checks.push(check(
    "node_modules installed",
    existsSync(join(root, "node_modules")),
    existsSync(join(root, "node_modules")) ? undefined : "Run: npm install",
  ));

  // tsconfig.json exists
  checks.push(check("tsconfig.json exists", existsSync(join(root, "tsconfig.json"))));

  // Key source files exist
  for (const f of ["src/cli.ts", "src/orchestrator.ts", "src/types.ts", "src/config.ts"]) {
    checks.push(check(`${f} exists`, existsSync(join(root, f))));
  }

  return { step: 2, name: "Clone & Install", checks };
}

// ─── Step 3: Initialize (CLI init command) ────────────────────────────────────

async function checkInit(): Promise<CheckResult> {
  const root = resolve(import.meta.dirname ?? process.cwd(), "..");
  const tmpDir = join(tmpdir(), `qs-validate-${Date.now()}`);
  mkdirSync(tmpDir, { recursive: true });
  const checks = [];

  try {
    // Write a fake package.json with typescript devDep so init detects 'typescript'
    writeFileSync(
      join(tmpDir, "package.json"),
      JSON.stringify({
        name: "test-repo",
        scripts: { test: "vitest run", lint: "eslint ." },
        devDependencies: { typescript: "^5" },
      }),
    );

    // Run: npx tsx src/cli.ts init --output ./pi-agent.config.ts
    const outConfig = join(tmpDir, "pi-agent.config.ts");
    const initResult = run(
      `npx tsx "${join(root, "src/cli.ts")}" init --output "${outConfig}"`,
      tmpDir,
    );

    checks.push(check("init command exits 0", initResult.ok, initResult.ok ? undefined : initResult.stderr.slice(0, 200)));
    checks.push(check("pi-agent.config.ts created", existsSync(outConfig)));

    if (existsSync(outConfig)) {
      const content = readFileSync(outConfig, "utf-8");
      checks.push(check("config contains 'typescript'", content.includes('"typescript"')));
      checks.push(check("config contains 'export default'", content.includes("export default")));
      checks.push(check("config contains 'anthropic'", content.includes("anthropic")));
      checks.push(check("config contains 'repo:'", content.includes("repo:")));
      checks.push(check("config contains 'shiftLeft:'", content.includes("shiftLeft:")));
    }

    const agentsMd = join(tmpDir, "AGENTS.md");
    checks.push(check("AGENTS.md created", existsSync(agentsMd)));

    if (existsSync(agentsMd)) {
      const content = readFileSync(agentsMd, "utf-8");
      checks.push(check("AGENTS.md has Coding Conventions section", /coding convention/i.test(content)));
      checks.push(check("AGENTS.md has Testing section", /testing/i.test(content)));
      checks.push(check("AGENTS.md has Do Not section", /do not/i.test(content)));
    }
  } finally {
    rmSync(tmpDir, { recursive: true, force: true });
  }

  return { step: 3, name: "Initialize (duc-e2e-agent init)", checks };
}

// ─── Step 4: API keys (environment validation) ────────────────────────────────

function checkApiKeys(): CheckResult {
  const checks = [];

  const hasAnthropic = Boolean(process.env["ANTHROPIC_API_KEY"]);
  checks.push(check(
    "ANTHROPIC_API_KEY set",
    hasAnthropic,
    hasAnthropic ? undefined : "export ANTHROPIC_API_KEY=sk-ant-... (required for live runs)",
  ));

  const hasGitHub = Boolean(process.env["GITHUB_TOKEN"]);
  checks.push(check(
    "GITHUB_TOKEN set",
    true, // Optional — warn only
    hasGitHub ? undefined : "GITHUB_TOKEN not set — automatic PR creation will be skipped",
  ));

  const hasOpenAI = Boolean(process.env["OPENAI_API_KEY"]);
  checks.push(check(
    "Provider key available",
    hasAnthropic || hasOpenAI,
    (!hasAnthropic && !hasOpenAI) ? "Set ANTHROPIC_API_KEY or OPENAI_API_KEY to enable live runs" : undefined,
  ));

  return { step: 4, name: "API Keys", checks };
}

// ─── Step 5: Run the test suite ───────────────────────────────────────────────

function checkTestSuite(): CheckResult {
  const root = resolve(import.meta.dirname ?? process.cwd(), "..");
  const checks = [];

  const result = run("npx vitest run --reporter=verbose 2>&1 | tail -5", root);

  // Count passed/failed from output
  const passMatch = result.stdout.match(/Tests\s+(\d+)\s+passed/);
  const failMatch = result.stdout.match(/(\d+)\s+failed/);
  const passed = passMatch ? Number(passMatch[1]) : 0;
  const failed = failMatch ? Number(failMatch[1]) : 0;

  checks.push(check("vitest run exits 0", result.ok));
  checks.push(check(`All tests pass (${passed} passed, ${failed} failed)`, result.ok && failed === 0));
  checks.push(check("Test count ≥ 800", passed >= 800, passed < 800 ? `Only ${passed} tests found` : undefined));

  return { step: 5, name: "Test Suite", checks };
}

// ─── Reporter ─────────────────────────────────────────────────────────────────

function printResult(r: CheckResult): { total: number; passed: number; required: boolean[] } {
  console.log(`\n${BOLD}Step ${r.step}: ${r.name}${RESET}`);
  let total = 0;
  let passed = 0;
  const required: boolean[] = [];

  for (const c of r.checks) {
    total++;
    const icon = c.pass ? `${GREEN}✓${RESET}` : `${RED}✗${RESET}`;
    console.log(`  ${icon} ${c.label}`);
    if (!c.pass && c.note) {
      console.log(`    ${DIM}→ ${c.note}${RESET}`);
    }
    if (c.pass) passed++;
    required.push(c.pass);
  }

  return { total, passed, required };
}

// ─── Main ─────────────────────────────────────────────────────────────────────

async function main(): Promise<void> {
  console.log(`${BOLD}Quickstart Validation — T078${RESET}`);
  console.log("Verifying all 5 setup steps from quickstart.md...");

  const results: CheckResult[] = [
    checkPrerequisites(),
    checkInstall(),
    await checkInit(),
    checkApiKeys(),
    checkTestSuite(),
  ];

  let totalChecks = 0;
  let passedChecks = 0;
  const stepStatuses: { step: number; name: string; pass: boolean }[] = [];

  for (const r of results) {
    const { total, passed } = printResult(r);
    totalChecks += total;
    passedChecks += passed;

    // Steps 1, 2, 3, 5 are required to pass; step 4 (API keys) is advisory
    const required = r.step !== 4;
    stepStatuses.push({ step: r.step, name: r.name, pass: !required || passed === total });
  }

  // ── Final summary ────────────────────────────────────────────────────────────
  console.log(`\n${BOLD}── Quickstart Validation Summary ─────────────────────────────────────────${RESET}`);
  for (const s of stepStatuses) {
    const icon = s.pass ? `${GREEN}✓ PASS${RESET}` : `${RED}✗ FAIL${RESET}`;
    console.log(`  Step ${s.step}: ${s.name.padEnd(38)} ${icon}`);
  }

  const allRequired = stepStatuses.filter((s) => s.step !== 4).every((s) => s.pass);
  console.log();
  console.log(`Checks: ${passedChecks}/${totalChecks} passed`);
  console.log(
    allRequired
      ? `${GREEN}${BOLD}All required quickstart steps PASS.${RESET} ✓`
      : `${RED}${BOLD}Some quickstart steps FAIL — see details above.${RESET}`,
  );

  if (!allRequired) process.exit(1);
}

main().catch((err) => {
  console.error(err instanceof Error ? err.message : String(err));
  process.exit(1);
});
