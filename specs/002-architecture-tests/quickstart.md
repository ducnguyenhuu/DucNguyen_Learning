# Quickstart: Architecture Tests (S3)

**Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md) · **Research**: [research.md](research.md)

Runs entirely on a development machine. No Azure, no Entra tenant, and — unlike S2 — no
database for the gates themselves. Only FR-019's behavioural test needs the SQL container.

---

## Prerequisites

| Requirement | Notes |
|---|---|
| .NET 10 SDK | `dotnet --version` → 10.0.x. Confirmed present: 10.0.105 |
| Docker Desktop or OrbStack | **Only** for FR-019's integration test and the existing S2 suite. Fifteen of the seventeen gates read only files and assembly metadata, so they need nothing running |

No new NuGet package is required. [research.md](research.md) R1 rejected adding an
architecture-testing library, so the gates use only what the solution already has.

---

## 1. Run the gates

```bash
dotnet test tests/ArchitectureTests/ArchitectureTests.csproj
```

The whole suite, as CI will run it once S7 exists:

```bash
dotnet test
```

Baseline entering this slice, for comparison against `SC-005`'s 5-minute bar:

| Suite | Tests | Duration |
|---|---|---|
| `Tenancy.UnitTests` | 112 | ~0.2 s |
| `Tenancy.IntegrationTests` | 85 | ~20 s |

Record the new total once `ArchitectureTests` exists. The gates are file and metadata reads,
so they should add well under a second — if they add meaningfully more, something is scanning
`bin/` or `obj/` and needs excluding.

---

## 2. Prove every gate can actually fail

**This is the step that makes the slice worth anything.** FR-023 requires each of the seventeen
gates to be demonstrated red against a deliberate violation before it is accepted. The
`testing` skill states the reason plainly: *an architecture test that never could have failed
is decoration*, and *a test that passed the first time it was ever run* is a red flag.

Work one gate at a time: introduce the violation, run the gate, confirm it fails **and names
the offender** (FR-024), then revert with `git checkout -- .`

**Where the demonstration gets recorded (FR-023, resolving CHK001):** the **"Demonstrated"**
column in each table below. When a proof task (T017, T023, T027, T032, T038, T044, T046, T049)
actually runs a gate red, it fills that gate's cell in with `<commit-hash> (YYYY-MM-DD)` —
the hash of the commit in which the proof was performed (typically the same commit that adds
or finalizes the gate's test), and the date it was run. `quickstart.md` itself is the living
record: no PR exists per-task (same reasoning T009 used for verification narrative), no new
file is needed, and the record sits directly next to the reproduction steps it documents. A
gate is not accepted per FR-023 until its cell is filled. Leave the cell as `_pending_` until
then — an empty cell and a filled one must be visually distinguishable at a glance.

| Gate | Introduce this violation | Expect | Demonstrated |
|---|---|---|---|
| FR-004 | Add `<PackageReference Include="Microsoft.EntityFrameworkCore" />` to `Tenancy.Domain.csproj` | Fails, naming project + package | _pending_ |
| FR-005 | Same, to `Tenancy.Application.csproj` | Fails, naming project + package | _pending_ |
| FR-008 | Add a project under `src/` outside `Tenancy.*` that references `Tenancy.Infrastructure` | Fails, naming the project | _pending_ |
| FR-010 | Add `ExecuteSqlRaw("SELECT 1")` in any repository not on the allow-list | Fails, naming file + member | _pending_ |
| FR-011 | Move the audited `ExecuteSqlInterpolatedAsync` call out of `RemoveMembershipAsync` into a new method, leaving the allow-list untouched | Fails — the allow-list binds file **and** member | _pending_ |
| FR-012 | Add a `BackgroundService` taking `TenancyDbContext` in its constructor | Fails, naming the type | _pending_ |
| FR-014 | Add any model-provider SDK package reference to `Tenancy.Application` | Fails, naming assembly + package | _pending_ |
| FR-015 | Put a model identifier string in `Tenancy.Application` | Fails, naming the location | _pending_ |
| FR-017 | Add `<PackageReference Include="FluentValidation" />` anywhere | Fails — ADR-021 ruling 1 | _pending_ |
| FR-018 | Add `<PackageReference Include="MediatR" />` anywhere | Fails — ADR-021 ruling 2 | _pending_ |
| FR-020 | Delete the coverage declaration from the only test covering one spec-001 requirement | Fails, naming that requirement | _pending_ |

The three absence pins (FR-009, FR-013, FR-016) prove the same way in reverse — introduce the
thing, confirm the pin fails, revert — and are given rows below. FR-023 now
names all seventeen explicitly — earlier drafts listed eleven, then sixteen, both disagreeing with
this file (CHK002, and analyze finding I1 which caught that FR-011 was proven here but absent there).

Two more were added by the checklist review, and the remaining four complete the seventeen — they
are listed as rows rather than left in prose, so counting rows gives the right number (analyze
finding I4):

| Gate | Introduce this violation | Expect | Demonstrated |
|---|---|---|---|
| FR-026 | Change any `IgnoreQueryFilters(["TenantFilter"])` call to the bare `IgnoreQueryFilters()` | Fails, naming file + member | _pending_ |
| FR-027 | Insert a `Membership` via `TenancyDbContext` without setting `CurrentTenantId` | Throws `DomainException` — already covered by `UnsetTenantContextWriteTests` | _pending_ |
| FR-009 | Add a second capability directory under `src/` | Absence pin fails, instructing you to extend FR-008's gate | _pending_ |
| FR-013 | Add any `BackgroundService` under `src/` | Absence pin fails | _pending_ |
| FR-016 | Add a model-provider SDK package reference | Absence pin fails, naming which of its two facts changed | _pending_ |
| FR-019 | See §3 — its proof is behavioural, not structural | Test fails against today's blanket `500` | _pending_ |

**FR-012 has no positive case while no background job exists.** Its proof is therefore a
temporary fixture that gets reverted, not a permanent test. That is inherent to writing the
guardrail before the first job — which the spec chose deliberately — and is worth stating in
the task's notes so a later reader does not mistake the missing permanent test for an
oversight.

---

## 3. Verify FR-019 behaviourally, not structurally

[research.md](research.md) R2 amended this requirement: instead of a gate detecting an
endpoint that *could* surface a `DomainException` as `500`, the failure mode is removed —
`ProblemDetailsHandler` maps `DomainException` → `400` and `ConflictException` → `409`
centrally.

Prove it two ways:

```bash
# Unit: the handler maps the two exception types to 400 and 409
dotnet test tests/Tenancy.UnitTests/Tenancy.UnitTests.csproj --filter "FullyQualifiedName~ProblemDetails"

# Integration: an endpoint that does NOT catch DomainException still yields 400, not 500
dotnet test tests/Tenancy.IntegrationTests/Tenancy.IntegrationTests.csproj --filter "FullyQualifiedName~ExceptionMapping"
```

Existing endpoint `catch` blocks keep working unchanged — they run before the handler is
reached, so their more specific messages are preserved. Confirm that by re-running the full
S2 suite and seeing the same pass count, not a smaller one.

---

## 4. Confirm the FR-006 refactor changed nothing observable

`Tenancy.Application` loses its `Microsoft.EntityFrameworkCore` package reference; the
`DbUpdateException` catches in `EnsureUserProvisioned` and `InviteMember` become catches of
an `Application`-owned type translated at the `Infrastructure` boundary.

```bash
# The reference is gone
grep -c "EntityFrameworkCore" src/Tenancy/Tenancy.Application/Tenancy.Application.csproj   # → 0

# Both race paths still behave identically
dotnet test tests/Tenancy.UnitTests/Tenancy.UnitTests.csproj --filter "FullyQualifiedName~EnsureUserProvisioned|FullyQualifiedName~InviteMemberTests"
```

**Order matters here and the plan fixes it**: `EnsureUserProvisioned`'s race path has no test
today, so its test is written and seen to pass against the *current* behaviour before the
refactor touches it. Reversing that order means changing untested code and calling the result
verified.

---

## Troubleshooting

| Symptom | Cause |
|---|---|
| A gate passes when you expected it to fail | The violation was introduced somewhere the scan does not look. Check whether the gate reads `src/` only, and whether `bin/`/`obj/` copies are being scanned instead of source |
| Raw-SQL gate misses a call you added | Source-text scanning is formatting-sensitive — a call split across lines or reached through an alias can evade it. This is a recorded residual risk in research.md R4; the escalation path is a Roslyn analyzer, not a looser regex |
| Gates are slow | Something is walking `bin/`, `obj/`, or `.git`. The gates should read four `.csproj` files, the `.cs` files under `src/`, and assembly metadata |
| `ArchitectureTests` will not compile after FR-006 | Expected mid-slice if FR-005's gate landed before the refactor. The plan sequences the refactor first for this reason |
| A migrated capability-boundary test fails after the move | Its repo-root discovery walks up from `AppContext.BaseDirectory` looking for `src/Tenancy`. A new project sits at a different depth, but the walk is depth-independent — check the project actually builds to the expected `bin/` path rather than changing the walk |
