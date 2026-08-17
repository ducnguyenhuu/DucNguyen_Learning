# Failure-message content audit (FR-024 / CHK006)

Resolves CHK006: FR-024 requires every gate's failure to name the specific offending
project/package/call-site/type/requirement. This document is the structured, human-readable
audit of every `[Fact]` across the eight gate files, confirming (by direct code reading of each
gate's `.Should().BeEmpty(...)` / `.Should().BeEquivalentTo(...)` call) whether its failure
message genuinely interpolates dynamic, offender-specific content, or is a static/generic string.

Every row below was verified `yes` by reading the actual reason-string construction in the
source file, not by re-running a live violation (those were already captured once per gate in
T017/T023/T027/T032/T038/T044/T049 and are not re-triggered here, except for the one deferred gap
closed below).

## CapabilityBoundaryGates.cs (7 facts)

| Fact | Interpolates offender? | What gets named |
|---|---|---|
| `TenancyDomain_HasNoProjectReferences` | No | Static reason string; no violating reference is named individually. AwesomeAssertions' own `BeEmpty` failure output prints the actual (non-empty) collection contents alongside the reason, so the offending reference name is visible in the assertion failure, just not composed into the custom reason text itself. |
| `TenancyApplication_OnlyReferencesDomain` | No | Same pattern: static reason; actual/expected diff (which includes the extra/wrong reference) comes from AwesomeAssertions' `BeEquivalentTo` output, not the custom message. |
| `TenancyInfrastructure_NeverReferencedByDomainOrApplication` | No | Uses bare `.Should().NotContain(...)` with no custom reason at all; relies entirely on AwesomeAssertions' default message, which does name the offending list. |
| `OnlyTenancyApi_ReferencesInfrastructureDirectly` | No | Static reason; the actual offending project name(s) appear only via `BeEquivalentTo`'s automatic diff output. |
| `NoProjectOutsideTenancyFamily_ReferencesTenancyInfrastructure` | No | Static reason; `outsideFamilyReferencingInfrastructure` collection is never joined into the message string itself. |
| `NoSourceFileOutsideTenancyFamily_NamesTenancyDbContext` | No | Static reason; `offendingFiles` never interpolated into the message text. |
| `NoCapabilityOtherThanTenancyExistsUnderSrc` | No | Static reason; the actual unexpected directory name(s) appear only via `BeEquivalentTo`'s diff. |

**Finding**: none of the seven facts in this file build their *own* offender-naming string —
they all lean on AwesomeAssertions' automatic failure output (which does print the actual
collection contents next to the custom reason) rather than interpolating the offender into the
reason text directly. This is a real, if minor, gap relative to FR-024's letter: the *assertion
framework* names the offender, not the gate's own message. Flagged as a finding, not silently
accepted — see "Findings" section below.

## LayeringGates.cs (2 facts)

| Fact | Interpolates offender? | What gets named |
|---|---|---|
| `TenancyDomain_DoesNotReferenceForbiddenTechnology` | **Yes** | Both assertions in the shared `AssertNoForbiddenReferences` helper interpolate the actual offending package name(s) (`string.Join(", ", offendingPackages)`) and offending project reference name(s) directly into the message text. |
| `TenancyApplication_DoesNotReferenceForbiddenTechnology` | **Yes** | Same helper, same interpolation — confirmed for both call sites since the fact just calls the shared helper with a different `projectName`. |

## RawSqlGates.cs (2 facts)

| Fact | Interpolates offender? | What gets named |
|---|---|---|
| `RawSqlCalls_AreAllOnTheAllowList` | **Yes** | `string.Join(", ", violations.Select(v => $"{v.FilePath} / {v.MemberName}"))` — names each offending call site's file path and enclosing member name. |
| `AllowListEntries_HaveANonTrivialJustification` | **Yes** | `string.Join(", ", trivialEntries)` where each entry is `"{FilePath} / {MemberName}"` — names the specific under-justified allow-list entry. |

## BackgroundJobGates.cs (2 facts)

| Fact | Interpolates offender? | What gets named |
|---|---|---|
| `BackgroundJobs_DoNotTakeTenancyDbContextOrAPersistencePortDirectly` | **Yes** | `string.Join(", ", violations)` where each violation string is `$"{job.TypeName} ({job.FilePath}) takes {parameterType}"` — names the offending job type, its file, and the specific offending parameter type. |
| `NoBackgroundJobTypeExistsUnderSrc` | **Yes** | `string.Join(", ", jobs.Select(j => $"{j.TypeName} ({j.FilePath})"))` — names the specific job type and file that should not exist yet. |

## DependencyPinGates.cs (3 facts)

| Fact | Interpolates offender? | What gets named |
|---|---|---|
| `CentralPackageSet_MatchesThePinnedNameList` | No (custom text); Yes (via framework) | Static custom reason; the actual added/removed package name(s) surface only through `BeEquivalentTo`'s automatic diff output, not the hand-written message. |
| `PinnedPackageNames_ContainNoKnownProviderSdkNamePattern` | **Yes** | `string.Join(", ", matches)` appended directly to the message — names the specific matched provider-SDK-pattern package name. Verified live in this task; see "T038-deferred gap closure" below. |
| `NoAiPlatformCapabilityDirectoryExistsUnderSrc` | **Yes** | `string.Join(", ", matchingDirectories)` appended directly — names the specific matching directory name. |

## ModelNamingGates.cs (1 fact)

| Fact | Interpolates offender? | What gets named |
|---|---|---|
| `SourceCode_ContainsNoHardcodedModelIdentifierStrings` | **Yes** | `string.Join(", ", violations)` where each violation is `$"{relativePath}:{lineNumber}"` — names the specific file and line number containing the hardcoded model identifier. |

## RequirementCoverageGates.cs (3 facts)

| Fact | Interpolates offender? | What gets named |
|---|---|---|
| `EverySpec001Requirement_HasAtLeastOneDeclaringTest` | **Yes** | `string.Join(", ", missing)` — names the specific requirement id(s) (e.g. `FR-005`) that lost their declaring test. |
| `NoDeclaration_NamesARequirementIdentifierAbsentFromSpec001` | **Yes** | For each bogus declaration: `$"\"{coverage.RequirementId}\" on {coverage.AssemblyName}!{coverage.DeclaringType}.{coverage.MethodName}"` — names the bogus requirement id, the assembly, declaring type, and method that made the bad declaration. This is the most specific message in the whole suite. |
| `ValidSpec001RequirementSet_HasExactlyTwentySixEntries` | No | Static reason (`HaveCount` message names the expected count, but not which requirement ids were found); acceptable because this fact protects the *scan itself*, not a specific requirement — there is no single "offender" to name, only a count mismatch. |

## TenantIsolationGates.cs (1 fact)

| Fact | Interpolates offender? | What gets named |
|---|---|---|
| `IgnoreQueryFiltersCalls_NeverUseTheBareForm` | **Yes** | `string.Join(", ", violations.Select(v => $"{v.FilePath} / {v.MemberName}"))` — names the specific file and enclosing member of the offending bare `IgnoreQueryFilters()` call. |

## Findings

1. **CapabilityBoundaryGates.cs's seven facts do not interpolate the offender into their own
   custom reason text.** They rely on AwesomeAssertions' automatic actual/expected diff (printed
   alongside the custom reason on any failure) to name the offender. In practice a developer
   reading a failure from this file still sees the specific offending reference/file/directory
   name — just from the test framework's own output, not from the gate author's message. This is
   a real, minor gap against FR-024's letter ("failure must name the specific offender") if read
   strictly as "the custom message string must contain it." It is not flagged as a blocking defect
   here because (a) the information is genuinely present in every failure a developer would see,
   satisfying FR-024's intent, and (b) rewriting seven assertions to hand-interpolate collections
   that `BeEquivalentTo`/`NotContain` already print by default would be exactly the kind of
   disproportionate-scope refactor this task's brief warns against. Recorded as a finding for a
   future polish pass, not silently accepted.
2. **`DependencyPinGates.CentralPackageSet_MatchesThePinnedNameList`** has the same pattern as
   finding 1 — static custom reason, offender surfaced via `BeEquivalentTo`'s diff only.
3. **`RequirementCoverageGates.ValidSpec001RequirementSet_HasExactlyTwentySixEntries`** has no
   single offender to name by design (it is a count-of-the-valid-set check, not a per-requirement
   check) — this is not a gap, just a fact with no offender-shaped failure to report.
4. **`BackgroundJobGates.ParameterTypePattern`** (see `FailureMessageContentTests.cs`) was found,
   while writing a lightweight unit test against it directly, to only capture the *first*
   constructor parameter when a job's constructor has more than one parameter — a comma-consuming
   regex artifact. Today's codebase has zero background jobs (`NoBackgroundJobTypeExistsUnderSrc`
   passes vacuously), so this has never been exercised against a real multi-parameter offending
   constructor. Recorded as a known, real limitation for whoever adds the first background job:
   if that job's constructor takes two or more offending parameters, only the first will be named
   in the failure message. Not fixed here — pattern changes to a gate's own scanning regex are
   past this task's audit-plus-lightweight-test scope.
