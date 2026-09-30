# Commit-Message Contract

**Branch**: `006-ci-cd` | **Date**: 2026-09-29
**Enforced by**: `infrastructure/scripts/validate-commit-messages.sh <base> <head>`

## Grammar (subject line)

```text
<type>[(<scope>)][!]: <description>
```

| Part | Rule |
|---|---|
| `type` | one of `feat fix chore docs style refactor perf test build ci` (from `CLAUDE.md`) |
| `scope` | optional; lowercase letters, digits, `-`; in parentheses |
| `!` | optional; marks a breaking change |
| `description` | required; at least one non-space character after `: ` |

Equivalent pattern:

```text
^(feat|fix|chore|docs|style|refactor|perf|test|build|ci)(\([a-z0-9-]+\))?!?: \S.*$
```

Only the first line is checked. Bodies and trailers (including `Co-Authored-By:`) are free-form.

## Which commits are checked

`git log --no-merges <base>..<head>`:
- pull request: `base` = merge base with `main`, `head` = PR head
- push to `main`: `base` = previous tip, `head` = new tip

**Merge commits are excluded** — Git and GitHub author them, and the existing history already
contains `Merge branch …` / `Merge pull request …` subjects.

## Output on failure

For each offending commit: short SHA, the subject as written, and the expected grammar with one
valid example. Exit code 1. Exit code 2 on usage errors (bad arguments), so a misconfigured job is
never mistaken for a clean pass.

## Examples

| Subject | Result |
|---|---|
| `feat(ci-cd): add supersession guard` | ✅ |
| `fix!: reject tokens without an allowed role` | ✅ |
| `fixed stuff` | ❌ no type |
| `Feat: add pipeline` | ❌ type must be lowercase |
| `feat:add pipeline` | ❌ space required after the colon |
| `Merge branch '005-terraform-azure'` | skipped — merge commit |
