# Implementation Plan: Containerization

**Branch**: `004-containerization` | **Date**: 2026-09-02 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/004-containerization/spec.md`

## Summary

Package the existing `Tenancy` service as a multi-stage, non-root, chiseled-base
container image, and give the repository a root `compose.yaml` that starts exactly three
services — the API, SQL Server, and the OTel Collector already configured in slice 003 —
from one documented command with no credential in any tracked file. The image gets a
`HEALTHCHECK` that reuses the existing `/health/ready` surface (via a tiny published probe
executable, because a chiseled image has no shell and no `curl`), an explicitly configured
finite shutdown budget, and a new *draining* readiness state so a terminating container
stops advertising itself as ready before it stops accepting work. Two repeatable scripts
close out the slice: a Trivy image secret scan that is proven able to fail against a
deliberately baited image, and a baseline recorder that captures image size (compressed and
uncompressed) and cold-start-to-ready with its measurement conditions. Nothing Azure,
Kubernetes, Helm, registry, or pipeline shaped is built here — those are S6 and S7.

## Technical Context

**Language/Version**: .NET 10, C# (ADR-002; unchanged from slices 001–003). SDK pinned by
`global.json` to 10.0.105 with `rollForward: latestFeature`
**Primary Dependencies**: No new NuGet package for the API. Build/runtime images
`mcr.microsoft.com/dotnet/sdk:10.0` and `mcr.microsoft.com/dotnet/aspnet:10.0-noble-chiseled-extra` (research.md R1: ICU/tzdata required by Microsoft.Data.SqlClient);
`mcr.microsoft.com/mssql/server:2022-latest` and the existing
`otel/opentelemetry-collector-contrib` for the composed stack; Trivy (Apache-2.0, single
binary) as the image secret scanner. One new tiny project, `Tenancy.HealthProbe`, exists
only so the image can have a `HEALTHCHECK` at all
**Storage**: SQL Server in a container for local use, reached by the existing
`ConnectionStrings:TenancyDb` configuration key — no schema change, no new table. Data lives
in a named volume so it survives `docker compose down` but not `down -v`
**Testing**: xUnit v3 + AwesomeAssertions (existing convention). Unit tests for the new
draining state and the probe's exit-code contract; a file-inspection gate test asserting no
credential literal and a non-root `USER` in tracked container configuration; container
runtime behaviour (effective uid, SIGTERM drain, secret scan, vulnerability scan, baseline)
proven by the documented scripts in `infrastructure/scripts/`, since this repo still has no
CI to run a Docker-in-test suite (S7)
**Target Platform**: Linux container, `linux/amd64` and `linux/arm64` for the API image;
SQL Server is amd64-only and runs under emulation on Apple Silicon (see research.md R2)
**Project Type**: Single service (`Tenancy`). This slice adds packaging and local
orchestration around the existing four-project layout plus one auxiliary probe project
**Performance Goals**: `docker compose up` reaches a ready, signed-in-able service inside
3 minutes on a clean checkout (SC-001), measured over three consecutive runs. Cold start to
`/health/ready`=200 for the API container alone (database already healthy) is recorded as a
baseline, not held to a target — the point of S5 is to establish the number
**Constraints**: Non-root (uid 1654) and a read-only root filesystem with a `tmpfs` `/tmp`;
no secret in any image layer, image config, or tracked file; a telemetry outage must not
affect readiness or a business request (inherited FR-006 of slice 003); the total shutdown
budget must fit inside the Compose grace period including OpenTelemetry's post-`StopAsync`
flush tail (arithmetic in research.md R4)
**Scale/Scope**: One application instance in the local stack. Multi-replica concerns —
ingress, rolling updates, pod disruption budgets, workload-identity secret injection — are
S6, and this slice deliberately only creates their seam
**Secrets**: Three inputs are required and none may be tracked: the SQL Server `sa` password,
the `TenancyDb` connection string built from it, and the existing `AzureAd` settings. All
three reach the container as environment variables interpolated from an untracked `.env`,
with a committed `.env.example` naming them; `${VAR:?message}` makes a missing value fail the
stack immediately with a readable message rather than falling back to a default password.
`.gitignore` already covers `.env`/`.env.*` with an `!.env.example` exception (added in slice
001), so no ignore-rule change is needed. .NET User Secrets stay the mechanism for the
`dotnet run` workflow; they are not visible inside a container, which is why the composed
stack uses environment variables instead

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I — Human approval for production/high-risk actions | ✅ Pass | Nothing here creates a path to production: no registry push, no deployment, no pipeline. `docker compose` is a developer-local command. No AI action |
| II — Architectural authority | ✅ Pass | ADR-001/002/007 (Azure, .NET, AKS) already settle the destination; ADR-011/018 settle the telemetry shape this stack wires up. No new ADR is required — a container image on AKS is what ADR-007 already decided. Two choices are *plan-level*, not architecturally significant, and are recorded in research.md rather than as ADRs: the chiseled base image and Trivy as the scanner. If Trivy later becomes the repository-wide scanning gate in S7, that promotion warrants an ADR then |
| III — Business-capability boundaries | ✅ Pass | No new service and no new data store. The composed SQL Server is the same `Tenancy`-owned database, running locally. The probe project is an auxiliary executable in the same service's image, not a service |
| IV — Tenant isolation | ✅ Pass | No new request path, endpoint, or query. Existing isolation tests (spec 002) are untouched and remain the gate. US1's authenticated tenant operation exercises them through the container rather than adding to them |
| V — Secure by default | ✅ Pass (this slice's second purpose) | Non-root, read-only root filesystem, no secret in layers or image config, credentials only via untracked environment interpolation, a secret scan that is *proven* able to detect one, and a fixed-threshold vulnerability scan (FR-012) satisfying the constitution's separate "Vulnerability scan" / "Container image scan" gates. See Technical Context "Secrets" |
| VI — Observable by default | ✅ Pass | The stack includes the Collector so the containerized service's telemetry is verifiable end to end; readiness gains a draining state, making shutdown observable rather than inferred. No telemetry is removed or weakened |
| VII — Automated gates over vigilance | ⚠️ Partial, justified | Three gates are automated in-repo: unit tests for the draining state and probe contract, and a tracked-file inspection test for credential literals and the non-root `USER`. Four are *repeatable scripts, not yet build-failing gates* — image secret scan, image vulnerability scan (FR-012), non-root runtime verification, and the baseline — because this repository has no CI at all yet (there is no `.github/workflows`; pipeline work is roadmap S7). Each is a single command with a pass/fail exit code, deliberately shaped so S7 wires it in without rework. This is a pre-existing repository gap, not one this slice introduces, and is recorded as such rather than described as done |
| VIII — Deterministic first | N/A | No AI capability |
| IX — AI provider abstraction | N/A | No AI invocation |
| X — Vertical slices | ✅ Pass | Ships a runnable stack a developer can sign in to, not a technical layer. Deferrals are explicit and seam-only: no Kubernetes manifest, no Helm chart, no registry, no migration-as-deployment-step machinery |
| XI — No individual measurement | ✅ Pass | The baseline measures an image and a process, never a person |

One partial: Principle VII's "gate that fails the build" cannot be fully satisfied while no
build pipeline exists. Recorded in Complexity Tracking below rather than waved through.

**Post-design re-check (after Phase 1)**: the design surfaced two things worth restating
rather than leaving in research.md. First, Principle V got *stronger* than the initial gate
assumed: `--image-config-scanners secret` covers the image config and build history, not only
the layers, so a secret passed as a build argument or `ENV` is in scope — and the negative
proof had to be redesigned once research showed Trivy silently allow-lists anything matching
`example` or any path containing `test`, which would have made the obvious FR-009 test pass
while proving nothing. Second, Principle VI is touched more than "no telemetry is removed"
implies: the new draining state adds a third readiness meaning, so slice 003's
`contracts/health-endpoints.md` promise that the response body distinguishes operational
situations for a human now has one more case to honour. No verdict in the table above changes.

## Project Structure

### Documentation (this feature)

```text
specs/004-containerization/
├── plan.md                          # This file
├── research.md                      # Phase 0 — the six decisions this slice turns on
├── data-model.md                    # Phase 1 — no new persisted entity; runtime/config contracts
├── quickstart.md                    # Phase 1 — the one command, and how to verify each claim
├── contracts/
│   ├── container-image.md           # Image contract: user, port, env, mounts, signals, probe
│   ├── compose-stack.md             # Service topology, ordering, .env variable contract
│   └── baseline-record.md           # Required fields of the recorded baseline
├── checklists/requirements.md       # Existing — passed before planning
└── tasks.md                         # Phase 2 output (/speckit.tasks — NOT created here)
```

### Source Code (repository root)

```text
Dockerfile                            # New — multi-stage: sdk build -> chiseled runtime
Dockerfile.secretbait                 # New — builds an intentionally leaky image, used only
                                      #   to prove the secret scan can fail (never shipped)
.dockerignore                         # New — keeps bin/obj, .env, user-secrets, .git out of
                                      #   build context (build speed AND leak prevention)
compose.yaml                          # New — api + sqlserver + otel-collector, one command
.env.example                          # New — names every required variable, holds no value

src/Tenancy/
├── Tenancy.Api/
│   ├── Program.cs                    # Extended — configure HostOptions.ShutdownTimeout;
│   │                                 #   register the draining health check; stop calling
│   │                                 #   UseHttpsRedirection when TLS terminates upstream
│   └── HealthChecks/
│       ├── StartupState.cs           # Extended — gains a terminal "stopping" state
│       └── StartupHealthCheck.cs     # Extended — reports draining distinctly from
│                                     #   not-yet-started and from a dependency failure
└── Tenancy.HealthProbe/              # New project — ~30 lines: HTTP GET a URL, exit 0 on
    ├── Program.cs                    #   200 and 1 otherwise. Exists because chiseled
    └── Tenancy.HealthProbe.csproj    #   images have no shell and no curl (research.md R1)

tests/
├── ArchitectureTests/
│   └── ContainerConfigurationGates.cs  # New — tracked container config contains no
│                                       #   credential literal; Dockerfile sets a non-root USER
├── Tenancy.UnitTests/
│   └── HealthChecks/
│       └── DrainingReadinessTests.cs   # New — not-started / ready / draining are three
│                                       #   distinguishable results
└── Tenancy.IntegrationTests/
    └── Observability/
        └── HealthCheckTests.cs         # Extended — /health/ready reports draining while
                                        #   /health/live stays healthy

infrastructure/scripts/
├── scan-image-secrets.sh             # New — Trivy secret scan of a built image, exit 1 on
│                                     #   any finding; also runs the bait image and FAILS if
│                                     #   the bait is not detected
├── scan-image-vulnerabilities.sh     # New — Trivy vulnerability scan of a built image at a
│                                     #   fixed HIGH,CRITICAL threshold (FR-012), exit 1 on
│                                     #   any unresolved finding — satisfies the constitution's
│                                     #   "Vulnerability scan" / "Container image scan" gates
└── measure-image-baseline.sh         # New — records size (compressed + uncompressed) and
                                      #   cold-start-to-ready over N runs, median and p90

docs/operations/
└── container-image-baseline.md       # New — the recorded baseline (FR-010), written by hand
                                      #   from the script's output, with conditions and revision
```

**Structure Decision**: Single service (`Tenancy`), unchanged. The `Dockerfile`,
`.dockerignore`, and `compose.yaml` sit at the repository root because the build context must
span `Directory.Build.props`, `Directory.Packages.props`, and `global.json`, and because
FR-004's "one documented command" is `docker compose up` typed at the checkout root with no
`-f`. The existing `deploy/otel-collector/docker-compose.yml` stays exactly as slice 003 left
it — it is the `dotnet run` workflow's collector, and the root `compose.yaml` reuses its
`config.yaml` rather than copying the configuration, so the two cannot drift.
`Tenancy.HealthProbe` is a peer project rather than a mode of `Tenancy.Api` so the probe can
be invoked without booting the API's host, and so its presence in the image is explicit.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Principle VII — three of six checks are scripts with exit codes rather than build-failing gates | The repository has no CI pipeline yet (no `.github/workflows`); wiring one is roadmap S7. Refusing to add the checks until S7 would leave FR-009 and FR-010 unproven for a whole slice | Building a pipeline here would import S7 wholesale into a one-week slice and would need registry, secret, and branch-protection decisions this slice has no basis to make. Each script is written as a single pass/fail command precisely so S7 adds a workflow step, not a rewrite |
| A new project (`Tenancy.HealthProbe`) whose only purpose is the container health check | A chiseled base image contains no shell and no HTTP client, and Microsoft ships no first-party probe utility (`dotnet/dotnet-docker#4300` is still open). FR-005 requires the container health status to use the existing readiness surface, which means something in the image must be able to make an HTTP request | Switching to the full `noble` base to get a shell was rejected: +39 MB compressed, a package manager and shell back in the image, and `curl` still is not installed. A third-party probe binary was rejected as a new unpinned dependency for thirty lines of code |
