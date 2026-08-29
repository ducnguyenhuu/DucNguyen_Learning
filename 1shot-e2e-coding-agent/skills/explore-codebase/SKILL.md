# Skill: Explore Codebase

**Node**: `context_gather`
**Tools**: `read`, `grep`, `find`, `ls` (read-only)
**Purpose**: Systematically explore the repository and identify every file relevant to the task before any code changes are made.

---

## When to Use This Skill

Use this skill at the start of every agent run, before planning or implementing changes. It ensures the implementation node receives an accurate list of files to read and modify.

---

## Step-by-Step Workflow

### 1. Start from the Root
Run `ls /workspace` to understand the top-level project structure: source directories, test directories, configuration files, and build artifacts.

### 2. Identify the Language and Framework
Check for well-known project files:
- `package.json` → Node.js (TypeScript / JavaScript)
- `pyproject.toml` / `setup.py` → Python
- `go.mod` → Go
- `pom.xml` / `build.gradle` → Java

Read the relevant config file to understand dependencies and scripts.

### 3. Read AGENTS.md (if present)
```
read /workspace/AGENTS.md
```
This file contains project-specific coding rules. Follow them throughout the run.

### 4. Find Relevant Files by Keyword
Use `grep` to locate files related to the task keywords:
```
grep -r "<keyword>" /workspace/src --include="*.ts" -l
grep -r "<keyword>" /workspace/tests --include="*.ts" -l
```
Start with the most specific keyword from the task description, then broaden if needed.

### 5. Trace the Call Graph
For each candidate file found in step 4:
- Read the file to understand its exports and imports
- Follow imports to related modules (one level deep is usually enough)
- Record every file that will need to be read or modified

### 6. Check Existing Tests
Find the test files that cover the code under change:
```
find /workspace/tests -name "*.test.ts" | xargs grep -l "<keyword>"
```
Note which test files exist — they constrain what the implementation must satisfy.

### 7. Summarise Findings
Output:
1. **Relevant files** — a bullet list of absolute paths, one per line, prefixed with `- `
2. **Understanding** — 2–4 sentences describing how the codebase achieves the goal and what changes are needed

---

## Rules

- Only use read-only tools: `read`, `grep`, `find`, `ls`
- Do **not** modify any files
- Do **not** guess file contents — always read before summarising
- If a file is > 500 lines, read only the relevant sections using line ranges
- Limit the total number of relevant files to ≤ 20 to stay within token budget
