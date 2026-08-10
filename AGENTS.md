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
running locally — is specified *and planned*:
[spec](specs/001-auth-tenant-management/spec.md) ·
[plan](specs/001-auth-tenant-management/plan.md) ·
[research](specs/001-auth-tenant-management/research.md) ·
[data model](specs/001-auth-tenant-management/data-model.md) ·
[contracts](specs/001-auth-tenant-management/contracts/openapi.yaml) ·
[quickstart](specs/001-auth-tenant-management/quickstart.md).
`/speckit.tasks` is next. **No application code exists yet.**

Before writing S2 code, read
[ADR-017](docs/adr/ADR-017-tenant-context-resolution.md) — tenant context comes from a
**validated route selector**, and it enumerates the only three operations permitted to run
without tenant context. A fourth would need the ADR amended.

Open decisions are recorded in
[docs/traceability.md](docs/traceability.md#open-decisions). They need a human, not an
agent. U6 is partially resolved (2026-08-09): performance testing is assigned to S7; E2E and
security test scheduling remain open.

---

*The two sections below are maintained by `.specify/scripts/bash/update-agent-context.sh`
from the current slice's `plan.md`. Everything above them is hand-written. Per ADR-016 this
is the single agent instruction file — there is no `CLAUDE.md`, deliberately.*

## Active Technologies
- C# 14 / .NET 10 LTS + ASP.NET Core 10, EF Core 10, Microsoft.Identity.Web 4.14.2 (001-auth-tenant-management)
- SQL Server 2022 (container) (001-auth-tenant-management)

## Recent Changes
