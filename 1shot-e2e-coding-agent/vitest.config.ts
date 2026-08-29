import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    globals: true,
    environment: "node",

    // Match all test files under tests/
    include: ["tests/**/*.test.ts"],
    exclude: ["node_modules", "dist"],

    // Per-test timeout: 30s (integration tests hit Docker / Pi SDK)
    testTimeout: 30_000,

    // Coverage via c8/v8 — matches what CI would report
    coverage: {
      provider: "v8",
      reporter: ["text", "json", "html"],
      include: ["src/**/*.ts"],
      // Exempt pure-type files and standalone scripts (Constitution Principle II)
      exclude: ["src/types.ts", "scripts/**"],
      thresholds: {
        lines: 80,
        branches: 75,
        functions: 80,
        statements: 80,
      },
    },
  },
});
