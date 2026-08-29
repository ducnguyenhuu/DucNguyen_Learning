<!--
  Sync Impact Report
  ==================
  Version change: N/A → 1.0.0 (initial ratification)
  Modified principles: N/A (first version)
  Added sections:
    - Core Principles (4 principles)
    - Quality & Delivery Standards
    - Cross-Document Consistency Protocol
    - Governance
  Removed sections: N/A
  Templates requiring updates:
    - .specify/templates/plan-template.md ✅ updated (Constitution Check aligned)
    - .specify/templates/spec-template.md ✅ updated (learning annotations added)
    - .specify/templates/tasks-template.md ✅ updated (unit test mandate + summary)
    - .specify/templates/checklist-template.md ✅ reviewed (no changes needed)
    - .specify/templates/agent-file-template.md ✅ reviewed (no changes needed)
  Follow-up TODOs: None
-->

# One-Shot E2E Coding Agent Constitution

## Core Principles

### I. Beginner-Friendly Explanations (NON-NEGOTIABLE)

Every technical decision, design pattern, architectural choice, and
implementation detail MUST include a plain-language explanation suitable
for a developer who is learning these concepts for the first time.

- All code MUST include inline comments explaining *why*, not just *what*.
- Design documents MUST define technical terms on first use
  (e.g., "Blueprint — a fixed sequence of steps the agent follows,
  like a recipe").
- Architecture decisions MUST include a "Why this matters" paragraph
  written for someone unfamiliar with the concept.
- When a concept has multiple possible approaches, MUST briefly name
  the alternatives and explain why this one was chosen.
- Acronyms MUST be spelled out on first use in every document.

**Rationale**: The primary user is learning. If the output is not
understandable, it has no value regardless of technical correctness.

### II. Unit Tests with Every Implementation (NON-NEGOTIABLE)

Every implementation task MUST be delivered with its corresponding
unit tests and a concise summary of what was implemented.

- Every code file MUST have a corresponding test file unless it is
  pure configuration or type definitions.
- Tests MUST be written to fail first (red), then implementation
  makes them pass (green), then refactor — the classic TDD cycle.
- Each completed task MUST include a summary block:
  - What was implemented (1-2 sentences).
  - What the tests verify (bullet list of test cases).
  - Any known limitations or edge cases not yet covered.
- Test coverage MUST target the critical paths first; exhaustive
  coverage is secondary to meaningful coverage.

**Rationale**: Tests prove the code works and serve as living
documentation. Summaries ensure the learner can review progress
without re-reading every file.

### III. Cross-Document Consistency (NON-NEGOTIABLE)

Any change to any document MUST trigger a review of all related
documents to ensure they remain consistent and aligned.

- When a spec changes, the plan, tasks, and checklists MUST be
  reviewed and updated to reflect the change.
- When a plan changes, the tasks MUST be reviewed and updated.
- When terminology changes in one document, all documents using
  that term MUST be updated.
- A "Consistency Check" section MUST appear in every PR or
  change summary, listing which documents were reviewed and
  whether updates were needed.
- Contradictions between documents are treated as bugs — they
  MUST be fixed before proceeding.

**Rationale**: Inconsistent documentation causes confusion and
wasted effort. A single source of truth across all artifacts
prevents the learner from following outdated or conflicting
instructions.

### IV. Justified Decisions with Selling Points

Every technical decision, tool choice, pattern selection, and
architectural trade-off MUST include explicit justification and
the key selling points that led to the choice.

- Decisions MUST state the problem being solved.
- Decisions MUST list at least 2 alternatives that were considered.
- Decisions MUST explain why the chosen option wins over the
  alternatives (the "selling points").
- Decisions MUST acknowledge trade-offs or downsides of the
  chosen option (honest assessment).
- Trivial decisions (e.g., variable naming) are exempt; the
  threshold is any choice that affects architecture, tooling,
  dependencies, or workflow.

**Rationale**: Justifications teach decision-making skills and
prevent cargo-cult choices. Selling points make it easy to
re-evaluate decisions when context changes.

## Quality & Delivery Standards

- Every implementation delivery MUST include: source code,
  unit tests, and a summary of what was built.
- Explanatory comments MUST use consistent style: `// Why:` for
  rationale comments, `// Note:` for important context.
- Decision records MUST follow a consistent format: Problem →
  Alternatives → Decision → Selling Points → Trade-offs.
- All documents MUST be written in Markdown with proper heading
  hierarchy.

## Cross-Document Consistency Protocol

When any document is modified, the author MUST:

1. Identify all documents that reference the changed content.
2. Review each referenced document for alignment.
3. Update any document that is now inconsistent.
4. Record the consistency check in the change summary:
   ```
   Consistency Check:
   - spec.md: reviewed, no changes needed
   - plan.md: updated Section X to match new terminology
   - tasks.md: updated T005 description
   ```

Documents in scope for consistency checks:
- `spec.md` — feature specification
- `plan.md` — implementation plan
- `tasks.md` — task breakdown
- `checklists/*.md` — quality checklists
- `constitution.md` — this file
- `initial_requirement.md` — original requirements

## Governance

This constitution supersedes all other project practices and
conventions. All work products MUST comply with these principles.

- **Amendment process**: Any principle can be updated by
  documenting the change rationale, updating this file, and
  running the Cross-Document Consistency Protocol.
- **Versioning**: This constitution follows semantic versioning:
  - MAJOR: Principle removed or fundamentally redefined.
  - MINOR: New principle added or existing one expanded.
  - PATCH: Clarification, typo fix, or wording improvement.
- **Compliance review**: Every PR or task completion MUST
  reference which principles were applied and confirm
  compliance in the summary.

**Version**: 1.0.0 | **Ratified**: 2026-03-12 | **Last Amended**: 2026-03-12
