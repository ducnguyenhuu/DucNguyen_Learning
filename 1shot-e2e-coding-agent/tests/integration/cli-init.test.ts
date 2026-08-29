/**
 * tests/integration/cli-init.test.ts — T068
 *
 * Integration tests for the CLI `init` command (US6, FR-018).
 *
 * All disk I/O is mocked — tests validate the end-to-end wiring of:
 *  1. Language auto-detection from project files (package.json, pyproject.toml,
 *     go.mod, pom.xml, build.gradle)
 *  2. Test/lint command detection from package.json scripts
 *  3. pi-agent.config.ts generation — valid TypeScript, correct defaults
 *  4. AGENTS.md creation when none exists
 *  5. AGENTS.md skip when one already exists
 *  6. --language flag overrides auto-detection
 *  7. --output flag sets config output path
 *  8. Working directory defaults to cwd, --cwd flag overrides
 *
 * NOTE: These tests are written BEFORE implementation (T069).
 * They will fail (RED) until T069 adds the `init` command to src/cli.ts.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { join } from "node:path";

// ─── Mocks — node:fs/promises ─────────────────────────────────────────────────

const { mkdirMock, writeFileMock, readFileMock, accessMock } = vi.hoisted(() => ({
  mkdirMock:     vi.fn().mockResolvedValue(undefined),
  writeFileMock: vi.fn().mockResolvedValue(undefined),
  readFileMock:  vi.fn(),
  accessMock:    vi.fn(),
}));

vi.mock("node:fs/promises", () => ({
  mkdir:     mkdirMock,
  writeFile: writeFileMock,
  readFile:  readFileMock,
  access:    accessMock,
}));

// ─── Mocks — runner (not used by init, but cli.ts imports it) ────────────────

vi.mock("../../src/runner.js", () => ({
  runAgent: vi.fn().mockResolvedValue({ status: "succeeded" }),
}));

// ─── Import CLI under test ────────────────────────────────────────────────────

import { createProgram } from "../../src/cli.js";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function parse(args: string[]) {
  return createProgram().parseAsync(["node", "pi-agent", ...args]);
}

/**
 * Get the content written for a given file suffix (e.g. "pi-agent.config.ts").
 * Returns null when no write call matched.
 */
function getWrittenContent(suffix: string): string | null {
  const call = writeFileMock.mock.calls.find((c) =>
    String((c as unknown[])[0]).endsWith(suffix),
  ) as [string, string, string] | undefined;
  return call ? call[1] : null;
}

const PACKAGE_JSON_TS = JSON.stringify({
  scripts: { test: "vitest run", lint: "eslint ." },
});

const PACKAGE_JSON_JS = JSON.stringify({
  scripts: { test: "jest", lint: "eslint ." },
});

const PYPROJECT_TOML = `
[tool.pytest.ini_options]
testpaths = ["tests"]
`;

const GO_MOD = "module github.com/user/myapp\n\ngo 1.21\n";

const POM_XML = "<project><artifactId>myapp</artifactId></project>";

// ─── 1. Language auto-detection ───────────────────────────────────────────────

describe("CLI init — language auto-detection", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    accessMock.mockRejectedValue(new Error("ENOENT")); // AGENTS.md absent by default
  });

  it("detects 'typescript' from package.json with typescript devDependency", async () => {
    const pkgJson = JSON.stringify({ devDependencies: { typescript: "^5" }, scripts: { test: "vitest run", lint: "eslint ." } });
    readFileMock.mockImplementation((path: string) => {
      if (String(path).endsWith("package.json")) return Promise.resolve(pkgJson);
      return Promise.reject(new Error("ENOENT"));
    });
    accessMock.mockImplementation((path: string) => {
      if (String(path).endsWith("package.json")) return Promise.resolve();
      return Promise.reject(new Error("ENOENT"));
    });

    await parse(["init"]);

    const config = getWrittenContent("pi-agent.config.ts");
    expect(config).toContain("typescript");
  });

  it("detects 'javascript' from package.json without typescript", async () => {
    readFileMock.mockImplementation((path: string) => {
      if (String(path).endsWith("package.json")) return Promise.resolve(PACKAGE_JSON_JS);
      return Promise.reject(new Error("ENOENT"));
    });
    accessMock.mockImplementation((path: string) => {
      if (String(path).endsWith("package.json")) return Promise.resolve();
      return Promise.reject(new Error("ENOENT"));
    });

    await parse(["init"]);

    const config = getWrittenContent("pi-agent.config.ts");
    expect(config).toContain("javascript");
  });

  it("detects 'python' from pyproject.toml", async () => {
    readFileMock.mockImplementation((path: string) => {
      if (String(path).endsWith("pyproject.toml")) return Promise.resolve(PYPROJECT_TOML);
      return Promise.reject(new Error("ENOENT"));
    });
    accessMock.mockImplementation((path: string) => {
      if (String(path).endsWith("pyproject.toml")) return Promise.resolve();
      return Promise.reject(new Error("ENOENT"));
    });

    await parse(["init"]);

    const config = getWrittenContent("pi-agent.config.ts");
    expect(config).toContain("python");
  });

  it("detects 'go' from go.mod", async () => {
    readFileMock.mockImplementation((path: string) => {
      if (String(path).endsWith("go.mod")) return Promise.resolve(GO_MOD);
      return Promise.reject(new Error("ENOENT"));
    });
    accessMock.mockImplementation((path: string) => {
      if (String(path).endsWith("go.mod")) return Promise.resolve();
      return Promise.reject(new Error("ENOENT"));
    });

    await parse(["init"]);

    const config = getWrittenContent("pi-agent.config.ts");
    expect(config).toContain("go");
  });

  it("detects 'java' from pom.xml", async () => {
    readFileMock.mockImplementation((path: string) => {
      if (String(path).endsWith("pom.xml")) return Promise.resolve(POM_XML);
      return Promise.reject(new Error("ENOENT"));
    });
    accessMock.mockImplementation((path: string) => {
      if (String(path).endsWith("pom.xml")) return Promise.resolve();
      return Promise.reject(new Error("ENOENT"));
    });

    await parse(["init"]);

    const config = getWrittenContent("pi-agent.config.ts");
    expect(config).toContain("java");
  });

  it("falls back to 'typescript' when no project files found", async () => {
    readFileMock.mockRejectedValue(new Error("ENOENT"));
    accessMock.mockRejectedValue(new Error("ENOENT"));

    await parse(["init"]);

    const config = getWrittenContent("pi-agent.config.ts");
    expect(config).toContain("typescript");
  });
});

// ─── 2. Test/lint command detection ──────────────────────────────────────────

describe("CLI init — test/lint command detection from package.json", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    accessMock.mockRejectedValue(new Error("ENOENT"));
  });

  it("extracts test command from package.json scripts.test", async () => {
    readFileMock.mockImplementation((path: string) => {
      if (String(path).endsWith("package.json")) return Promise.resolve(PACKAGE_JSON_TS);
      return Promise.reject(new Error("ENOENT"));
    });
    accessMock.mockImplementation((path: string) => {
      if (String(path).endsWith("package.json")) return Promise.resolve();
      return Promise.reject(new Error("ENOENT"));
    });

    await parse(["init"]);

    const config = getWrittenContent("pi-agent.config.ts");
    expect(config).toContain("vitest run");
  });

  it("extracts lint command from package.json scripts.lint", async () => {
    readFileMock.mockImplementation((path: string) => {
      if (String(path).endsWith("package.json")) return Promise.resolve(PACKAGE_JSON_TS);
      return Promise.reject(new Error("ENOENT"));
    });
    accessMock.mockImplementation((path: string) => {
      if (String(path).endsWith("package.json")) return Promise.resolve();
      return Promise.reject(new Error("ENOENT"));
    });

    await parse(["init"]);

    const config = getWrittenContent("pi-agent.config.ts");
    expect(config).toContain("eslint .");
  });

  it("uses default 'npm test' when scripts.test is absent", async () => {
    const pkg = JSON.stringify({ scripts: { lint: "eslint ." } });
    readFileMock.mockImplementation((path: string) => {
      if (String(path).endsWith("package.json")) return Promise.resolve(pkg);
      return Promise.reject(new Error("ENOENT"));
    });
    accessMock.mockImplementation((path: string) => {
      if (String(path).endsWith("package.json")) return Promise.resolve();
      return Promise.reject(new Error("ENOENT"));
    });

    await parse(["init"]);

    const config = getWrittenContent("pi-agent.config.ts");
    expect(config).toMatch(/npm test|vitest run|pytest/);
  });

  it("uses default pytest when language is python", async () => {
    readFileMock.mockImplementation((path: string) => {
      if (String(path).endsWith("pyproject.toml")) return Promise.resolve(PYPROJECT_TOML);
      return Promise.reject(new Error("ENOENT"));
    });
    accessMock.mockImplementation((path: string) => {
      if (String(path).endsWith("pyproject.toml")) return Promise.resolve();
      return Promise.reject(new Error("ENOENT"));
    });

    await parse(["init"]);

    const config = getWrittenContent("pi-agent.config.ts");
    expect(config).toMatch(/pytest/);
  });
});

// ─── 3. Config file generation ────────────────────────────────────────────────

describe("CLI init — pi-agent.config.ts generation", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    readFileMock.mockRejectedValue(new Error("ENOENT"));
    accessMock.mockRejectedValue(new Error("ENOENT"));
  });

  it("writes a config file", async () => {
    await parse(["init"]);
    expect(writeFileMock).toHaveBeenCalled();
    const config = getWrittenContent("pi-agent.config.ts");
    expect(config).not.toBeNull();
  });

  it("generated config is valid TypeScript (exports default)", async () => {
    await parse(["init"]);
    const config = getWrittenContent("pi-agent.config.ts") ?? "";
    expect(config).toMatch(/export default/);
  });

  it("generated config contains agent section", async () => {
    await parse(["init"]);
    const config = getWrittenContent("pi-agent.config.ts") ?? "";
    expect(config).toContain("agent:");
  });

  it("generated config contains provider section defaulting to anthropic", async () => {
    await parse(["init"]);
    const config = getWrittenContent("pi-agent.config.ts") ?? "";
    expect(config).toContain("anthropic");
  });

  it("generated config contains repo section", async () => {
    await parse(["init"]);
    const config = getWrittenContent("pi-agent.config.ts") ?? "";
    expect(config).toContain("repo:");
  });

  it("generated config includes shiftLeft section with maxRetries", async () => {
    await parse(["init"]);
    const config = getWrittenContent("pi-agent.config.ts") ?? "";
    expect(config).toMatch(/shiftLeft:|maxRetries/);
  });

  it("writes to ./pi-agent.config.ts by default", async () => {
    await parse(["init"]);
    const writtenPath = writeFileMock.mock.calls.find((c) =>
      String((c as unknown[])[0]).endsWith("pi-agent.config.ts"),
    )?.[0] as string | undefined;
    expect(writtenPath).toBeDefined();
    expect(String(writtenPath)).toMatch(/pi-agent\.config\.ts$/);
  });
});

// ─── 4. AGENTS.md creation ───────────────────────────────────────────────────

describe("CLI init — AGENTS.md creation", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    readFileMock.mockRejectedValue(new Error("ENOENT"));
  });

  it("creates AGENTS.md when none exists", async () => {
    // access throws ENOENT for everything — AGENTS.md absent
    accessMock.mockRejectedValue(new Error("ENOENT"));

    await parse(["init"]);

    const agentsMd = getWrittenContent("AGENTS.md");
    expect(agentsMd).not.toBeNull();
  });

  it("AGENTS.md contains coding conventions section", async () => {
    accessMock.mockRejectedValue(new Error("ENOENT"));

    await parse(["init"]);

    const agentsMd = getWrittenContent("AGENTS.md") ?? "";
    expect(agentsMd).toMatch(/convention|Coding|Rules|rule/i);
  });

  it("AGENTS.md contains testing rules", async () => {
    accessMock.mockRejectedValue(new Error("ENOENT"));

    await parse(["init"]);

    const agentsMd = getWrittenContent("AGENTS.md") ?? "";
    expect(agentsMd).toMatch(/test|Test/);
  });

  it("does not overwrite existing AGENTS.md", async () => {
    // AGENTS.md exists (access resolves for it)
    accessMock.mockImplementation((path: string) => {
      if (String(path).endsWith("AGENTS.md")) return Promise.resolve();
      return Promise.reject(new Error("ENOENT"));
    });

    await parse(["init"]);

    const agentsMd = getWrittenContent("AGENTS.md");
    expect(agentsMd).toBeNull();
  });
});

// ─── 5. --language flag ───────────────────────────────────────────────────────

describe("CLI init — --language flag overrides auto-detection", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Even if package.json exists and says typescript, --language should win
    readFileMock.mockResolvedValue(
      JSON.stringify({ devDependencies: { typescript: "^5" }, scripts: { test: "vitest run", lint: "eslint ." } }),
    );
    accessMock.mockRejectedValue(new Error("ENOENT"));
  });

  it("--language python sets python in the generated config", async () => {
    await parse(["init", "--language", "python"]);
    const config = getWrittenContent("pi-agent.config.ts") ?? "";
    expect(config).toContain("python");
  });

  it("--language go sets go in the generated config", async () => {
    await parse(["init", "--language", "go"]);
    const config = getWrittenContent("pi-agent.config.ts") ?? "";
    expect(config).toContain("go");
  });

  it("-l short form is accepted", async () => {
    await parse(["init", "-l", "java"]);
    const config = getWrittenContent("pi-agent.config.ts") ?? "";
    expect(config).toContain("java");
  });
});

// ─── 6. --output flag ────────────────────────────────────────────────────────

describe("CLI init — --output flag sets config output path", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    readFileMock.mockRejectedValue(new Error("ENOENT"));
    accessMock.mockRejectedValue(new Error("ENOENT"));
  });

  it("--output writes config to the specified path", async () => {
    await parse(["init", "--output", "/tmp/my-agent.config.ts"]);
    const writtenPath = writeFileMock.mock.calls.find((c) =>
      String((c as unknown[])[0]).endsWith("my-agent.config.ts"),
    )?.[0] as string | undefined;
    expect(String(writtenPath)).toContain("my-agent.config.ts");
  });

  it("-o short form is accepted", async () => {
    await parse(["init", "-o", "/tmp/custom.config.ts"]);
    const writtenPath = writeFileMock.mock.calls.find((c) =>
      String((c as unknown[])[0]).endsWith("custom.config.ts"),
    )?.[0] as string | undefined;
    expect(String(writtenPath)).toContain("custom.config.ts");
  });
});

// ─── 7. init command exists in the CLI ───────────────────────────────────────

describe("CLI init — command registration", () => {
  it("init is a registered subcommand (does not throw 'unknown command')", async () => {
    readFileMock.mockRejectedValue(new Error("ENOENT"));
    accessMock.mockRejectedValue(new Error("ENOENT"));
    await expect(parse(["init"])).resolves.not.toThrow();
  });
});
