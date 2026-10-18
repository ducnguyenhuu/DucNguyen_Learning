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

## Code comments

Comments explain **why the code is the way it is**, in terms a reader can verify from the
code and the domain alone.

**Never cite a task, requirement, or checklist identifier in code** — no `T058`, no
`FR-021`, no `SC-004`, no `CHK023`. Those live in `specs/`, which is working material for
one slice; once the slice ships they may be archived, and the comment then points at
nothing a reader can resolve or check.

**ADR references are fine.** ADRs are permanent, numbered, and live in
[docs/adr/](docs/adr/).

Keep the reasoning, drop the citation:

```csharp
// Wrong — T027 is unresolvable once the slice is archived
// Sets CurrentTenantId first because the interceptor (T027) stamps Added entities.

// Right — same reasoning, no dangling reference
// Set the tenant context before saving: the save interceptor stamps every newly added
// tenant-owned entity with whatever ambient tenant is current, so without this the new
// membership would be written against the wrong tenant.
```

Task lists in `specs/*/tasks.md` **do** carry these identifiers — that is their job. They
stop at the task list.

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

**Slice 3** — Observability — is complete:
[spec](specs/003-observability/spec.md) ·
[plan](specs/003-observability/plan.md) ·
[research](specs/003-observability/research.md) ·
[data model](specs/003-observability/data-model.md) ·
[quickstart](specs/003-observability/quickstart.md). It shipped OpenTelemetry
traces/metrics/logs correlated by a W3C `traceparent`-propagated identifier (present on
every span and structured log line for a request), tenant/user enrichment on spans and
logs only (never as a metric dimension, per ADR-018's cardinality concern), `/health/live`
and `/health/ready` health checks reflecting real dependency reachability, a DB-trigger-
enforced append-only audit log for tenant-mutating actions and authorization refusals, a
local OTel Collector (`deploy/otel-collector/`) for offline development, and a New Relic
OTLP backend switch that is configuration-only (`Observability:OtlpEndpoint` /
`Observability:NewRelicApiKey`, read in `OpenTelemetryExtensions.cs`) — no vendor SDK/agent
is referenced anywhere in the solution (ADR-011/ADR-018).

**Slice 4** — Containerization — is complete:
[spec](specs/004-containerization/spec.md) ·
[plan](specs/004-containerization/plan.md) ·
[research](specs/004-containerization/research.md) ·
[data model](specs/004-containerization/data-model.md) ·
[quickstart](specs/004-containerization/quickstart.md). It shipped a multi-stage `Dockerfile`
on `aspnet:10.0-noble-chiseled-extra` (non-root uid 1654, read-only root filesystem, exec-form
`ENTRYPOINT`/`HEALTHCHECK`), a root `compose.yaml` starting exactly the API, SQL Server, and
the existing OTel Collector with every credential interpolated from an untracked `.env`, a
third `Draining` readiness state so a terminating container stops advertising itself before
it stops accepting work, and two repeatable scripts — `scan-image-secrets.sh` (proven able to
fail against a deliberately baited image) and `scan-image-vulnerabilities.sh` — plus a
recorded image-size/cold-start baseline
([docs/operations/container-image-baseline.md](docs/operations/container-image-baseline.md)).
`aspnet:10.0-noble-chiseled` (without `-extra`) was the initial choice and was corrected after
container testing showed `Microsoft.Data.SqlClient` cannot open a connection under the
Invariant Globalization plain chiseled forces — see research.md R1. A second correction from
the same testing: `PosixSignalRegistration.Create`'s `PosixSignalContext.Cancel` must be set
`true` explicitly, or the default terminate-on-SIGTERM action still runs after a registered
handler returns — see Program.cs's `earlyShutdown` registration and research.md R4.

---

*The two sections below are maintained by `.specify/scripts/bash/update-agent-context.sh`
from the current slice's `plan.md`. Everything above them is hand-written. Per ADR-016 this
is the single agent instruction file — there is no `CLAUDE.md`, deliberately.*

## Active Technologies
- C# 14 / .NET 10 LTS + ASP.NET Core 10, EF Core 10, Microsoft.Identity.Web 4.14.2 (001-auth-tenant-management)
- SQL Server 2022 (container) (001-auth-tenant-management)
- No new dependencies — architecture gates use .csproj parsing, source scanning, and reflection; NetArchTest rejected on evidence, see specs/002-architecture-tests/research.md R1 (002-architecture-tests)
- OpenTelemetry SDK + OTLP exporter (never a vendor SDK/agent, per ADR-011/ADR-018); ASP.NET Core health checks; a DB-trigger-enforced append-only AuditEntries table (003-observability)
- Multi-stage container image on `aspnet:10.0-noble-chiseled-extra` (non-root uid 1654, no shell; `-extra` required because `Microsoft.Data.SqlClient` needs ICU/tzdata, see research.md R1); local `compose.yaml` of api + SQL Server 2022 + the existing OTel Collector; Trivy for image secret and vulnerability scanning; a tiny `Tenancy.HealthProbe` executable because chiseled images have no `curl` (004-containerization)
- HCL (Terraform ≥ 1.9) for infrastructure; Bash for orchestration scripts + azurerm provider (~> 4.0), azuread provider (~> 3.0) (005-terraform-azure)
- Azure Storage Account (Terraform remote state); Azure SQL (application data) (005-terraform-azure)
- GitHub Actions workflow YAML; Bash for gate scripts; JavaScript (k6) for the load test; HCL (Terraform ≥ 1.9) for identities and repository configuration; C# 14 / .NET 10 for the authorization-policy change + GitHub Actions (`actions/checkout`, `actions/setup-dotnet`, `azure/login`, `grafana/setup-k6-action`), gitleaks, Trivy (existing S5 scripts), NuGet Audit (built into the .NET SDK), Terraform providers `azurerm` ~> 4.0, `azuread` ~> 3.0, `integrations/github` ~> 6.0 (006-ci-cd)
- No new application storage. Pipeline evidence lives in GitHub (run history, job summaries, deployment records, artifacts); the SC-003 measurement is copied into `docs/operations/load-test-baseline.md` as the permanent record (006-ci-cd)

## Recent Changes
- 006-ci-cd: `.github/workflows/pipeline.yml` (gates, then deploy to dev, load test, production approval) and `gate-selftest.yml`; scripts in `.github/scripts/` and `infrastructure/scripts/`; Terraform roots `infrastructure/terraform/persistent/` (pipeline identities, app role) and `infrastructure/github/` (ruleset, environments, variables); NuGet Audit enforced in `Directory.Build.props`; the API's default authorization policy admits only `access_as_user` or `Tenancy.Automation.Member` (ADR-022)
