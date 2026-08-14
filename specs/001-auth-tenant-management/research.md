# Phase 0 Research: Auth + Tenant + Persistence (S2)

**Date**: 2026-08-09 · **Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md)

Every decision below is either forced by an existing ADR (recorded as such) or is a new
choice with its alternatives stated. Where a decision is architecturally significant, it
is escalated to an ADR rather than settled here — Constitution Principle II requires the
record, and Principle I reserves the approval for a human.

---

## R1. Tenant context resolution — the one that needed an ADR

**This is the most consequential unknown in the slice, and it exposed a real conflict in
the existing guidance.**

ADR-013 says tenant context is "resolved once per request from the authenticated
principal's membership, **never from a client-supplied parameter that is trusted**". The
`security` skill states it more absolutely: "**Never** from a route parameter, query
string, header, or body the caller controls."

But FR-010 requires a single user to hold membership in multiple tenants, and FR-007
requires every request to resolve to **exactly one** tenant. A caller in three tenants
must therefore be able to say which one they mean. Read absolutely, the skill's wording
forbids the only mechanism that satisfies FR-010.

**Resolution — the distinction is *selector* vs *grant*:**

> The client may **name** a candidate tenant. It may never **grant** itself access to one.
> Authorization is decided by a server-side membership lookup keyed on the authenticated
> principal. The route value is an input to that lookup, never a substitute for it.

ADR-013's actual wording already permits this — the operative word is *trusted*, and a
validated selector is not a trusted one. The `security` skill overstates it. Per Principle
II (a skill must not override an ADR, and disagreement is raised rather than resolved
unilaterally), two follow-ups:

- **Proposed [ADR-017](../../docs/adr/ADR-017-tenant-context-resolution.md)** — written as
  `Status: Proposed`, awaiting human approval. Must be Accepted before implementation.
- The `security` skill's absolute phrasing needs a clarifying amendment so the next reader
  does not conclude the design violates it. Tracked as a task, not done silently.

**Decision**: route-scoped selector — `/tenants/{tenantId}/...` — validated against
membership on every request, failing **closed** (404, indistinguishable from non-existent)
when no active membership matches.

**Rationale**: the tenant is visible in the URL, so which tenant a request touches is
evident in logs, traces, and telemetry rather than hidden in a header; it is idiomatic REST
sub-resource modelling; and it makes the "one tenant per request" rule structural rather
than conventional.

**Alternatives considered**:

| Alternative | Rejected because |
|---|---|
| `X-Tenant-Id` header | Same trust properties, but the tenant disappears from the URL — worse for logs, traces, and cache keys, and easier to forget on a new endpoint. |
| Tenant baked into the access token | Our tenants are not Entra tenants (see R2). Would require a token exchange per tenant switch and couple our tenancy to Entra's, contradicting the domain model. |
| Session-held "current tenant" server-side | Introduces server state, makes requests non-idempotent in a way FR-020 must then work around, and hides the tenant from the request entirely. |

### The three operations that cannot be tenant-scoped

This analysis is the security core of the slice. Exactly three operations legitimately run
**without** a resolved tenant context, and each is a potential leak path:

| Operation | Why it cannot be tenant-scoped | Required guard |
|---|---|---|
| `POST /tenants` | No tenant exists yet. | No tenant-scoped read occurs; creator becomes first Administrator in the same transaction. |
| `GET /tenants` | Lists the caller's memberships, which span tenants by definition. | Must query `Membership` **by `UserId`**, in a single audited helper, with the tenant filter explicitly bypassed by name and `UserId == caller` non-negotiable. |
| `POST /invitations/{token}/accept` | The caller has no membership yet — that is what accepting creates. | Authorization is the invitation token plus identity match (FR-013), not membership. |

Everything else is tenant-scoped and goes through the global filter. These three are
enumerated here so they can be listed in review and tested individually — an
unenumerated exception is how the filter gets quietly bypassed a fourth time.

---

## R2. Entra ID identity — the stable user identifier

**Decision**: `Microsoft.Identity.Web` 4.14.2 over raw `JwtBearer`, configured via
`AddMicrosoftIdentityWebApi`. It configures
`Microsoft.AspNetCore.Authentication.JwtBearer` 10.0.10 with Entra-correct issuer and
audience validation rather than leaving those to be hand-rolled.

**Decision**: the stable identity (FR-003) is the composite **`(tid, oid)`**, mapped to an
internal `UserId` we own.

This is the finding most likely to have been got wrong by assumption. `oid` is immutable
per user **within one Entra tenant** — it is deliberately *not* globally unique, so the
same human in two Entra tenants has two different `oid` values. Keying on `oid` alone
would collide across Entra tenants.

| Claim | Verdict |
|---|---|
| `oid` + `tid` | **Use this.** Immutable, non-reusable, unique as a pair. |
| `sub` | Rejected — pairwise per application registration. A second app registration yields a different `sub` for the same person. |
| `preferred_username` | Display only. Mutable. Microsoft's docs state explicitly it must not be used for authorization decisions. |
| `email` | Never key on it. Mutable and not guaranteed present. |

Consequences for the model: `User` carries `(EntraTenantId, EntraObjectId)` under a unique
index, and the internal `UserId` is what `Membership` references. Our `TenantId` is **never**
derived from `tid` — a customer's Entra tenant and our tenant are independent concepts.

**Configuration decisions**:
- Set `accessTokenAcceptedVersion: 2` in the app registration. v1 tokens have a different
  issuer format and no `preferred_username`, so claim-reading code silently differs.
- Set `MapInboundClaims = false` so claims stay as `oid`/`tid`/`scp` rather than being
  rewritten to long schema URIs. **Production code and test handler must agree on claim
  names** — disagreement here is the classic "tests green, production 403" bug.

**Local development** (no Azure, per spec Dependencies): an app registration needs only a
free Entra tenant, no subscription. The API is a token *validator*, so it holds **no client
secret at all** — which incidentally satisfies FR-026 with nothing to leak. A public-client
registration with PKCE and `http://localhost` yields test tokens via
`az account get-access-token --resource api://{clientId}`.

---

## R3. Tenant isolation in EF Core 10 — and precisely where it does not hold

**Decision**: global query filter applied by model iteration over an `ITenantOwned` marker,
with the tenant id read as a **member access on the DbContext instance** (`this.TenantId`),
not a captured local. EF lifts the member access to a SQL parameter, so one cached plan
serves all tenants; inlining it as a constant produces a per-tenant compiled model and a
genuine staleness risk.

**Decision**: use **EF Core 10 named query filters** —
`HasQueryFilter("TenantFilter", ...)`. Before EF 10 a second `HasQueryFilter` silently
overwrote the first and `IgnoreQueryFilters()` could only disable everything at once. Named
filters let `GET /tenants` (R1) bypass **only** the tenant filter, by name, in an audited
helper. **A bare no-argument `IgnoreQueryFilters()` is prohibited** — it disables every
filter including tenancy, and is exactly the call that would turn R1's audited exception
into a general-purpose leak.

**Decision**: a scoped `SaveChangesInterceptor` stamps `TenantId` on inserts and rejects any
modify/delete whose original `TenantId` differs from the resolved context. Query filters are
read-side only — EF issue #24122 — so nothing stops an attached stub entity carrying a
foreign tenant's key from being written without this guard. `ISaveChangesInterceptor` is not
a singleton interceptor, so it can safely take the scoped tenant context by DI.

**Decision**: `AddDbContext` (scoped), **not** `AddDbContextPool`. Pooling makes the context
effectively a reused singleton whose `OnConfiguring` runs once, so it cannot carry
per-request tenant state without a scoped factory wrapper. That complexity buys nothing at
this slice's scale.

**Decision**: compiled models (`dotnet ef dbcontext optimize`) must **not** be enabled — they
do not support global query filters at all (efcore#24897). Recorded here so a future
performance pass does not silently remove the isolation mechanism.

### The bypass list

The filter is the load-bearing isolation mechanism, so knowing where it does not apply is
not trivia — it is the threat model. These bypass or defeat it:

| # | Bypass | Mitigation in this slice |
|---|---|---|
| 1 | `IgnoreQueryFilters()` (no-arg) | Prohibited. Named form only, in audited helpers. S3 gate. |
| 2 | `Find` / `FindAsync` | **Prohibited in tenant-scoped code.** By design (efcore#9405, closed "not planned") it skips filters. Use `SingleOrDefaultAsync(x => x.Id == id)`. |
| 3 | Change-tracker / identity-map hits | Contained by the tenant being fixed for the DbContext's lifetime — one scope, one tenant, never two. |
| 4 | `ExecuteSqlRaw`, `SqlQuery<T>`, any raw SQL | **Correction (T075, 2026-08-12):** this row originally read "None in this slice." That is now stale — T075 legitimately introduced one `ExecuteSqlInterpolatedAsync` call (`MembershipRepository.cs`, a `SELECT ... WITH (UPDLOCK, HOLDLOCK)` row lock) for the last-administrator race-safety mechanism. It was reviewed and accepted at the time (see `.superpowers/sdd/tasks/progress.md`, Task 75); this row was simply never updated to reflect it. It is parameterized (no string concatenation), scoped to a single audited helper, and remains the *only* raw-SQL call site in the slice. S3's architecture test restricting raw SQL to audited helpers ([U12](../../docs/traceability.md)) still applies and would need to allow-list this call. |
| 5 | `FromSql*` | Version-sensitive across EF 3.x/5.x. Not used. If ever used, assert behaviour with a test rather than trusting docs. |
| 6 | `ExecuteUpdate` / `ExecuteDelete` | Filters *appear* to apply (shared query pipeline) but the change tracker is bypassed entirely — so **the interceptor does not run and concurrency tokens are not checked**. Not used in this slice. Research flagged this as undocumented; if adopted, assert the generated `WHERE`. |
| 7 | Owned types / complex types | Filters on owned types are ignored (efcore#18534, open). Tenant scoping comes from the owner. `Tenant.Settings` is owned — acceptable, documented. |
| 8 | Derived types in TPH/TPT | Filters may only sit on the root. No inheritance in this model. |
| 9 | `SaveChanges` generally | Covered by the interceptor above. |
| 10 | Anything outside EF | Nothing outside EF touches the database in this slice. |

Items 4 and 6, plus background jobs, are the paths ADR-013 names as its known weakness and
that S3 must close by gate. This slice's job is to not create any of them, and to leave the
list written down.

---

## R4. Integration test authentication

**Decision**: two tiers, because one does not cover the risk.

- **Tier 1 (default)**: a custom `Test` authentication scheme injected via
  `WebApplicationFactory.ConfigureTestServices`, driven by **request headers**
  (`X-Test-Oid`, `X-Test-Tid`) rather than mutable shared state — so one expensive host is
  shared across the suite and tests stay parallel-safe. Real authorization middleware, real
  policies, real tenant resolution all stay in the loop; only the identity *source* is
  replaced.
- **Tier 2 (a handful)**: self-signed RSA JWTs with `TokenValidationParameters` overridden
  and `ConfigurationManager` nulled out, exercising the actual `JwtBearerHandler`. This is
  the only tier that catches a misconfigured audience/issuer or a `MapInboundClaims`
  mismatch — failures Tier 1 is structurally blind to.

**Critical detail**: the ASP.NET Core docs' sample handler succeeds unconditionally, which
silently disables every 401 test. The handler must return `AuthenticateResult.NoResult()`
when no `Authorization` header is present, so FR-002 remains testable.

A mock OIDC server was considered and rejected — it additionally covers metadata retrieval
and key rollover, which are not part of this slice's risk surface.

---

## R5. Database container — and an Apple Silicon trap

**Decision**: Testcontainers (`Testcontainers.MsSql` 4.11.0) for integration tests, not a
compose-managed database. Per-run isolation, random ports, readiness waiting, automatic
cleanup. Compose arrives in S5 for running the app, which is a different job.

**Decision**: pin `mcr.microsoft.com/mssql/server:2022-latest`. Never `2025-latest`.

This matters specifically on this machine (Darwin ARM64) and would have cost real time:

- **Azure SQL Edge is retired** (30 Sep 2025) and had already dropped ARM64. The common
  older advice to use it on Apple Silicon is dead.
- `mssql/server` has **no native arm64 engine** — it runs under Docker Desktop's Rosetta
  emulation. Claims of "ARM64 compatible" 2025 images mean *runs emulated*, not native.
- **SQL Server 2025 RTM crashes on Docker Desktop for macOS**: it requires AVX
  instructions, which Rosetta does not implement. Fixed only in
  `2025-CU1-ubuntu-24.04`; the RTM tag was never patched.

Practical consequences to expect: emulated startup of 20–60s, ≥4GB to the Docker VM, and
Rosetta emulation enabled in Docker Desktop settings.

**Decision**: `Respawn` 6.2.1 to reset state between tests, with `__EFMigrationsHistory`
ignored. Transaction-rollback isolation was rejected — it requires the system under test to
enlist in the test's ambient transaction, which breaks the moment a request crosses the HTTP
boundary, and these are API-level tests.

**Decision**: **xUnit v3** (`xunit.v3` 3.2.2). The deciding feature is
`AssemblyFixtureAttribute`: one container per test assembly, which on emulated SQL Server is
the difference between a fast suite and an unusable one. v2 would force `[Collection]` onto
every class and serialize the suite. Note v3 is a rename, not an upgrade — test projects
become `Exe`, and `IAsyncLifetime` now returns `ValueTask`.

---

## R6. Idempotency (FR-020)

**Decision**: hand-rolled, ~150 lines, as an endpoint filter — **not** middleware (which
runs before routing and model binding, so it cannot see the endpoint or the bound body) and
not a library.

**Decision**: store idempotency records in **SQL Server, committed in the same transaction
as the business write**. A cache-backed store (which is what `IdempotentAPI` offers) can
lose the record and admit the duplicate, which defeats the point.

**Decision**: the unique primary key `(TenantId, Endpoint, Key)` **is** the concurrency
control — insert-and-catch-duplicate, no distributed lock. Keys are scoped per tenant
because a global key namespace is itself a cross-tenant information leak.

Semantics follow IETF draft `draft-ietf-httpapi-idempotency-key-header-07` (Standards
Track, not yet an RFC): replay returns the **stored status and body verbatim** (a `201`
replays as `201`, not `200`); same key with a different body payload is **422**; a request
still in flight is **409** with `Retry-After`. TTL 24 hours. `InFlight` rows older than 60s
are reclaimable so a crashed process cannot wedge a key permanently.

There is **no first-party ASP.NET Core idempotency feature** through .NET 10 — anything
claiming otherwise is describing a hand-rolled filter.

---

## R7. Concurrency (FR-021)

**Decision**: SQL Server `rowversion` via `.IsRowVersion()` on `Tenant`, `Membership`, and
`Invitation`. Database-generated, covers the whole row, no application bookkeeping.
(`xmin` is PostgreSQL-only and does not apply here.)

**Decision**: surface it as HTTP, not as an exception. `rowversion` is exposed as a base64
`ETag`; mutating endpoints require `If-Match`.

| Situation | Response |
|---|---|
| `If-Match` absent where required | **428** Precondition Required |
| `If-Match` stale, detected before save | **412** Precondition Failed |
| Race detected at `SaveChanges` | **409** Conflict |

All as `application/problem+json` (RFC 9457). A `DbUpdateConcurrencyException` reaching the
client as a 500 is a defect — FR-022 requires the problem be identified without internal
detail.

---

## R8. Migrations (SC-007)

**Decision**: `await db.Database.MigrateAsync()` at startup, **guarded to Development
only**, for this slice.

**Decision**: the production path is decided now and deferred in implementation:
`dotnet ef migrations bundle` run as a Kubernetes Job / init container with a
**separate DDL-privileged identity**, while the application's own SQL identity holds DML
rights only. Belongs to S6/S7. It is recorded here so the dev shortcut never becomes the
deployment mechanism by default — which is the documented failure mode.

Microsoft's guidance is unambiguous that `Migrate()` at startup is not acceptable in
production: concurrent instances, elevated DDL permissions for the app identity, no
rollback, and nobody reviews the SQL. EF 9+ added migration locking which mitigates only
the first of those four.

**Decision**: add `dotnet ef migrations has-pending-model-changes` to the build. EF 9+
throws on pending model changes; catching it in CI beats catching it at deploy.
`EnsureCreated()` is prohibited — it bypasses migrations and then makes `Migrate()` fail.

---

## R9. Assertion library — a licensing trap

**Decision**: **avoid FluentAssertions 8+**. Its licence changed to the Xceed Community
License, which is free for non-commercial use only. The `testing` skill's example
(`.Should().BeTrue()`) is FluentAssertions syntax and would pull this in by imitation.

**Recommendation**: `AwesomeAssertions` (MIT fork of FluentAssertions 7) to keep the same
syntax with no licence question, or `Shouldly`, or plain xUnit asserts.

*Confidence: high on the licence change, medium on the current best-regarded fork. Worth a
30-second check before pinning — this is a cheap thing to verify and an annoying one to
discover later.*

---

## R10. Unresolved — success criteria that cannot be verified in this slice

Not resolvable by research; they need a human scoping decision. Raised rather than quietly
dropped.

| Criterion | Problem | Proposed |
|---|---|---|
| **SC-003** — 95% of reads under 1s at 50 concurrent users / 20 tenants | Requires a load test. Performance tests are unscheduled per [U6](../../docs/traceability.md). Roadmap S2's *Done when* does not list it. | Either add a lightweight k6/NBomber check to S2, or explicitly defer SC-003 to the slice that schedules performance testing. **Do not silently skip it.** |
| **SC-001 / SC-002** — time-to-first-tenant under 5 min, invitation-to-data under 2 min, "without documentation" | Both measure a user interface. UI is out of scope for S2. | Measure the API path as a proxy via [quickstart.md](quickstart.md) and record the real number, flagging that the "without documentation" clause remains unverified until a UI exists. |
| **SC-008** — no secret in source control *including history* | Needs a history-scanning tool run locally; pipeline secret scanning is S7. | Add `gitleaks detect --no-git=false` (or trufflehog) as a documented local step in S2's definition of done. |

---

## Consolidated technology decisions

| Concern | Decision | Version |
|---|---|---|
| Runtime | .NET (LTS) | 10.0.105 installed; LTS to Nov 2028 |
| Auth | Microsoft.Identity.Web | 4.14.2 |
| JWT | Microsoft.AspNetCore.Authentication.JwtBearer | 10.0.10 |
| ORM | EF Core SQL Server | 10.0.x |
| Database | SQL Server in a container | `mssql/server:2022-latest` (ARM/Rosetta safe) |
| Test framework | xunit.v3 | 3.2.2 |
| Test host | Microsoft.AspNetCore.Mvc.Testing | 10.0.10 (must match ASP.NET Core exactly) |
| DB for tests | Testcontainers.MsSql | 4.11.0 |
| State reset | Respawn | 6.2.1 |
| Assertions | AwesomeAssertions or Shouldly — **not** FluentAssertions 8+ | see R9 |
| Package management | Central Package Management (`Directory.Packages.props`) | — |
