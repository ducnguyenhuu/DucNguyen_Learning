# AGENTS.md — Project Rules for AI Agents

## Coding Conventions
- Follow existing code patterns and naming conventions in the repository
- Use type annotations for all function parameters and return types
- Write docstrings/JSDoc comments for public functions and exported symbols
- Keep changes minimal and focused on the requested task
- Prefer editing existing files over creating new ones

## Testing
- Every new feature or changed behaviour must have corresponding tests
- Test file naming: `test_<module>.py` (Python) or `<module>.test.ts` (TypeScript/JavaScript)
- Use pytest fixtures for test setup in Python; beforeEach/afterEach in Jest/Vitest
- All tests must pass before pushing changes or creating a PR

## File Editing
- Files ≤250 lines: rewrite completely with `write`
- Files >250 lines: use `edit` for surgical, targeted changes
- Always read a file before editing it — never guess at existing content
- Confirm the exact surrounding context before making a replacement

## Do Not
- Do not modify configuration files (tsconfig.json, package.json, pyproject.toml, etc.) unless explicitly instructed
- Do not change import ordering or formatting — let the configured formatter handle it
- Do not add debugging statements (print, console.log, debugger) to committed code
- Do not install new dependencies without explicit instruction
- Do not commit secrets, tokens, API keys, or credentials
- Do not generate or guess URLs unless you are confident they are correct
