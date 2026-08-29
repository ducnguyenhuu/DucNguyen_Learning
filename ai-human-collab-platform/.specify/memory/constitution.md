<!--
SYNC IMPACT REPORT
==================
Version change: 0.0.0 → 1.0.0 (MAJOR - Initial constitution ratification)

Modified principles: N/A (initial version)

Added sections:
- Core Principles (5 principles)
- Development Constraints
- Quality Gates
- Governance

Removed sections: N/A (initial version)

Templates requiring updates:
- .specify/templates/plan-template.md: ✅ Compatible (Constitution Check section present)
- .specify/templates/spec-template.md: ✅ Compatible (requirements structure aligns)
- .specify/templates/tasks-template.md: ✅ Compatible (phase structure supports principles)

Follow-up TODOs: None
-->

# Project Constitution

## Core Principles

### I. Token-First Design

Every feature MUST target maximum token reduction through efficient data handling.

**Rules:**
- Tools MUST filter responses in the execution sandbox before returning data
- Response payloads MUST contain only essential fields required for the use case
- Aggregated summaries MUST be preferred over raw data dumps
- Lazy loading MUST be used for related resources unless explicitly requested
- Target: 95%+ token reduction vs traditional MCP approaches

**Rationale:** Context window is a finite, expensive resource. Traditional MCP tools
load schemas (~8,500 tokens per tool) at session start and return verbose responses.
Slash commands and code execution eliminate schema overhead (0 tokens until invoked)
and enable in-sandbox filtering.

### II. CLI-First Interface

Every library capability MUST be exposed through a command-line interface.

**Rules:**
- All functionality MUST be accessible via CLI commands
- Input MUST be accepted via stdin, arguments, and configuration files
- Output MUST go to stdout (data) and stderr (errors/diagnostics)
- JSON output format MUST be supported for machine consumption
- Human-readable format SHOULD be supported for interactive use
- Exit codes MUST follow Unix conventions (0 = success, non-zero = error)

**Rationale:** CLI interfaces enable Claude Code skills to invoke tools without
MCP overhead. Text-based I/O ensures debuggability, composability with Unix tools,
and straightforward testing.

### III. Code Execution Over MCP

Tools MUST be TypeScript client libraries executed in the sandbox, NOT MCP servers.

**Rules:**
- Tools MUST NOT define MCP tool schemas that load at session start
- Tools MUST be importable TypeScript modules with typed exports
- Claude Code skills MUST invoke tools via Bash command execution
- All data processing MUST occur within the execution sandbox
- Tools MUST be stateless between invocations

**Rationale:** MCP servers load tool schemas at session start, consuming context
before any work begins. With 40+ tools, this reaches 340k+ tokens. Slash commands
load 0 tokens until invoked, enabling complex multi-tool workflows.

### IV. Shared Infrastructure

Tools MUST maximize code reuse through the monorepo's shared utilities.

**Rules:**
- HTTP clients MUST use `@tools-hub/shared` utilities
- Error handling MUST use standard error classes from shared package
- Input validation MUST use shared validators where applicable
- Common types MUST be defined in shared package, not duplicated
- Tool-specific utilities MAY exist but MUST NOT duplicate shared functionality

**Rationale:** Consistent infrastructure reduces bugs, ensures uniform behavior,
and simplifies maintenance. Contributors benefit from battle-tested utilities
rather than reinventing solutions.

### V. Production-Ready Quality

All code MUST meet production-grade quality standards.

**Rules:**
- TypeScript strict mode MUST be enabled
- All public functions MUST have JSDoc documentation
- All inputs MUST be validated before processing
- All errors MUST be handled with informative messages
- Test coverage MUST be 80%+ for all packages
- No hardcoded credentials or secrets in code

**Rationale:** Tools are used in production workflows where failures have real
impact. Quality standards ensure reliability, security, and maintainability.

## Development Constraints

### Technology Stack

- **Language**: TypeScript (strict mode required)
- **Runtime**: Node.js 18+
- **Monorepo**: npm workspaces
- **Testing**: Native Node test runner
- **Linting**: ESLint + Prettier
- **CI/CD**: GitHub Actions

### Directory Structure

Every tool MUST follow this architecture:

```
tool-name/
├── src/
│   ├── index.ts          # Public exports
│   ├── core/             # HTTP client, auth, types
│   ├── operations/       # Business logic (CRUD)
│   └── utils/            # Tool-specific utilities
├── bin/                  # CLI entry points
├── .claude/skills/       # Claude skill definitions
├── README.md             # Quick start guide
└── package.json
```

### File Naming Conventions

- **kebab-case** for files: `health-check.ts`, `reference-resolver.ts`
- **PascalCase** for classes: `ToolError`, `HttpClient`
- **camelCase** for functions/variables: `fetchItem`, `validateInput`
- **SCREAMING_SNAKE_CASE** for constants: `API_BASE_URL`, `DEFAULT_TIMEOUT`

## Quality Gates

All changes MUST pass these gates before merge:

| Gate | Command | Requirement |
|------|---------|-------------|
| Build | `npm run build` | No errors |
| Lint | `npm run lint` | No warnings |
| Format | `npm run format:check` | Code properly formatted |
| Test | `npm test` | All pass, 80%+ coverage |
| Type Check | `tsc --noEmit` | No type errors |
| Token Analysis | Manual review | 95%+ reduction documented |

## Governance

### Amendment Process

1. Propose changes via pull request to this file
2. Document rationale for changes
3. Obtain maintainer approval
4. Update version according to semantic versioning:
   - **MAJOR**: Principle removal or backward-incompatible redefinition
   - **MINOR**: New principle added or existing principle materially expanded
   - **PATCH**: Clarifications, typo fixes, non-semantic refinements
5. Update Last Amended date

### Compliance Review

- All pull requests MUST verify compliance with these principles
- Code reviews MUST include constitution compliance check
- Complexity beyond these constraints MUST be justified in PR description

### Precedence

This constitution supersedes all other documentation when conflicts arise.
Runtime guidance documents (README, skill definitions) MUST align with
these principles.

**Version**: 1.0.0 | **Ratified**: 2026-01-21 | **Last Amended**: 2026-01-21
