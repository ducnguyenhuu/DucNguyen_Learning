# Skill: Implement Feature

**Node**: `implement`
**Tools**: `read`, `grep`, `find`, `ls`, `write`, `edit`, `bash`
**Purpose**: Execute a structured change plan precisely — read every file before touching it, make minimal diffs, and validate each change with a quick syntax check.

---

## When to Use This Skill

Use this skill inside the `implement` agent node, after the `plan` node has produced a structured list of files to modify and the changes to make in each.

---

## Pre-Implementation Checklist

Before writing any code:

1. **Re-read the plan** to understand the full scope of changes.
2. **Read every file you will modify** — never edit based on memory or assumptions.
3. **Identify shared types or interfaces** that multiple files depend on — change those first.
4. **Check for existing tests** for each file you'll modify — understand the contract the tests enforce.

---

## File Editing Strategy

### Size-Based Decision Rule

| File size    | Preferred tool | Rationale |
|--------------|----------------|-----------|
| ≤ 250 lines  | `write`        | Rewrite the whole file for simplicity |
| > 250 lines  | `edit`         | Surgical replacement — leave untouched lines intact |
| New file     | `write`        | Always create with full content |

### Edit Discipline
- **Always read before you edit** — run `read <file>` immediately before the edit call
- Include **3–5 lines of unchanged context** on both sides of the target in `edit` old-string
- Make one logical change per `edit` call — do not bundle unrelated changes
- After editing, re-read the changed region to verify correctness

---

## Implementation Order

1. **Shared types and interfaces first** (e.g. TypeScript types, Python dataclasses)
2. **Core logic modules** (services, utilities, domain logic)
3. **Consumers** (controllers, CLI handlers, API routes)
4. **Tests last** — update or add tests after the implementation is stable

---

## Validation After Each File

After writing or editing a file, run a quick syntax check:

```bash
# TypeScript
bash("npx tsc --noEmit --skipLibCheck 2>&1 | head -20")

# Python
bash("python -m py_compile <file> && echo OK")

# Go
bash("go vet ./...")
```

Fix any syntax errors before moving to the next file.

---

## Rules

- Follow the plan precisely — do **not** make changes outside the stated scope
- Do **not** add print/console.log debugging statements
- Do **not** change import ordering or formatting — let the configured formatter handle it
- Do **not** install new dependencies without explicit instruction
- Write a brief summary when all changes are complete:  
  `"All changes applied. <one sentence describing what was done>."`
