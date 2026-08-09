# AGENTS.md

Instructions for any AI coding agent working in this repository. Agent-neutral by
design (`idea.md` §38, ADR-016) — nothing here assumes a specific tool.

## Read this first

**Start at [roadmap.md](roadmap.md) page 1.** It states which of the 15 slices is
current. Work only on that slice.

## The rules that override everything

The [Constitution](.specify/memory/constitution.md) is the engineering law of this
repository — 11 principles, all binding. Read it before your first change. The four
most likely to be violated by accident:

1. **Principle I — humans own intent, architecture, risk, and authorization.** Do not
   expand scope beyond the task. If the work seems to need more, stop and ask. Never
   deploy to production.
2. **Principle II — authority is hierarchical.** Product direction → product spec →
   Constitution → architecture → ADRs → feature spec → plan → code → skills. A skill
   never overrides an ADR. **If an ADR looks wrong, propose a change; do not work
   around it.**
3. **Principle IV — tenant isolation.** Every tenant-scoped operation resolves to
   exactly one tenant, and cross-tenant access must be impossible, not unlikely.
4. **Principle VIII — deterministic first.** Rule out a deterministic solution before
   reaching for AI. Scoring and thresholds are arithmetic; AI explains them.

## Authority order, condensed

```
Constitution  >  ADRs  >  feature spec  >  plan  >  tasks  >  skills
```

When two sources conflict, the left one wins. When you cannot tell, ask.

## Before you write code

1. Read the current slice in [roadmap.md](roadmap.md) — its **Scope** and, more
   importantly, its **Not in scope**.
2. Read the feature spec under [specs/](specs/).
3. Read the relevant ADRs in [docs/adr/](docs/adr/). Do not re-derive a decision that
   is already recorded.
4. Load only the skills relevant to the task (`idea.md` §41) from
   [.agent/skills/](.agent/skills/) — not all of them.
5. Inspect the existing code. Match its conventions.

Tasks are guidance, not a to-do list to execute blindly (`idea.md` §35).

## Definition of done

A slice is done when its **Proof** checklist in roadmap.md is fully checked. Not when
the code compiles, and not when it works on the happy path.

This project is research-first (`idea.md` §59.2): **a technology is not proven until it
has been driven under failure conditions.** Service Bus needs a duplicate handled and a
dead letter replayed. Multi-tenancy needs a test that actually caught a cross-tenant
read. Demonstrating the happy path proves nothing worth knowing.

## Reporting

State outcomes faithfully. If a test fails, say so and show the output. If you skipped
a step, say which. If something is unverified, say it is unverified. Do not describe
work as complete when it is partially done — that is the failure mode that costs the
most to recover from.

## Commits

Conventional Commits, CI-enforced:

```
<type>(<scope>): <description>
```

Types: `feat` `fix` `chore` `docs` `style` `refactor` `perf` `test` `build` `ci`

Commit only when asked. If on the default branch, branch first.

## Repository map

| Path | Contents |
|------|----------|
| `.specify/memory/constitution.md` | **The engineering law.** Authoritative location. |
| `roadmap.md` | The 15 slices, in order. Page 1 is the plan. |
| `idea.md` | Product vision and architecture blueprint. The *why*. |
| `docs/adr/` | Architecture decisions. Binding. |
| `docs/traceability.md` | idea.md compliance audit + open decisions |
| `docs/architecture/` | Domain model, system architecture |
| `specs/` | Feature specifications, one directory per slice |
| `.agent/skills/` | Project knowledge skills. `.claude/skills` symlinks here. |
| `src/` | Services. Created by the slice that needs them, not up front. |
| `tests/` | Unit, Integration, Contract, Architecture, EndToEnd |
| `infrastructure/terraform/` | All infrastructure. No manual portal changes. |
| `deployment/` | Helm charts and Kubernetes manifests |

## Current state

Slice 1 (Constitution + ADRs) is complete. **Slice 2** — auth, tenant, persistence,
running locally — is specified in
[specs/001-auth-tenant-management/](specs/001-auth-tenant-management/spec.md) and is
next. No application code exists yet.

Six open decisions are recorded in
[docs/traceability.md](docs/traceability.md#open-decisions). They need a human, not an
agent.
