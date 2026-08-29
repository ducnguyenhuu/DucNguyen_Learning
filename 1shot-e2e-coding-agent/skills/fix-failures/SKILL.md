# Skill: Fix Failures

**Node**: `fix_failures`
**Tools**: `read`, `grep`, `find`, `ls`, `write`, `edit`, `bash`, `run_test`, `run_lint`
**Purpose**: Diagnose failing tests or lint errors and apply the smallest correct fix, without introducing regressions or oscillating between broken states.

---

## When to Use This Skill

Use this skill inside the `fix_failures` agent node, after `testStep` has reported one or more failing tests. The full test output is provided in the prompt.

---

## Step-by-Step Workflow

### 1. Parse the Failure Output

Read the test output carefully:
- Identify the **exact test names** that are failing
- Note the **assertion error messages** (expected vs. received)
- Note the **file paths** and **line numbers** where the failure occurred

Do not guess — use the output verbatim.

### 2. Read the Failing Test File

```
read <test-file-path>
```

Understand what the test expects. The test is the source of truth — do not change the test unless it has a clear bug.

### 3. Read the Implementation File

```
read <implementation-file-path>
```

Find the function or logic that the test is exercising. Understand why it produces the wrong result.

### 4. Diagnose the Root Cause

Common failure patterns:

| Symptom | Likely cause |
|---------|-------------|
| `Expected X but received Y` | Wrong return value or off-by-one |
| `TypeError: undefined is not a function` | Missing export, wrong import path |
| `Cannot read property of undefined` | Null/undefined not guarded |
| `Timeout exceeded` | Async function not awaited, or infinite loop |
| Lint error: `'x' is defined but never used` | Dead code or missing reference |

### 5. Oscillation Guard

Before making a fix, check the error hash stored in `ctx.errorHashes`:
- If this exact failure has appeared in a previous retry, do **not** apply the same fix again
- Instead, look for a different root cause or raise the issue clearly in the summary

### 6. Apply the Fix

Use the [implement-feature skill](../implement-feature/SKILL.md) editing discipline:
- Read the file immediately before editing
- Make the smallest possible change that makes the test pass
- Do not change unrelated code

### 7. Verify the Fix

Run the specific failing test(s) using the `run_test` tool:
```
run_test("<test-file>")
```

If it passes, run the full suite with `run_test("all")` to confirm no regressions.

Run the linter if any files were modified:
```
run_lint("<modified-file>")
```

Fix any new lint errors before concluding.

### 8. Report the Outcome

On success:
```
"Fixed: <one sentence describing the root cause and fix applied>."
```

On failure (after exhausting approaches):
```
"Unable to fix: <one sentence describing what was tried and why it did not work>."
```

---

## Rules

- Do **not** modify test files unless the test itself contains a clear bug (wrong expectation)
- Do **not** suppress errors with try/catch unless the original code used that pattern
- Do **not** add `// @ts-ignore` or `# type: ignore` suppression comments
- Do **not** apply the same fix twice in successive retries (oscillation)
- Constrain changes to files directly related to the failing test
