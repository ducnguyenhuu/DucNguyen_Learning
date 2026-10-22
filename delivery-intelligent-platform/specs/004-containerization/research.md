# Phase 0 Research: Containerization

**Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md)

The spec's quality checklist recorded no `NEEDS CLARIFICATION` markers, so nothing here
resolves an ambiguity in *what* to build. What follows are the six *how* decisions the slice
turns on, each of which had a plausible alternative that would have been wrong for a
different reason. Every factual claim below was verified against vendor documentation or
source on 2026-09-02; where verification failed, that is stated rather than smoothed over.

---

## R1. Runtime base image and the health-check problem

**Decision (revised after container testing — see below)**:
`mcr.microsoft.com/dotnet/aspnet:10.0-noble-chiseled-extra`, `USER $APP_UID` (uid 1654), and a
`HEALTHCHECK` in exec form invoking a purpose-built probe executable published into the image.

**Correction, found only by running the built container against real SQL Server (T014)**: the
initial decision below (plain `chiseled` + forced `InvariantGlobalization=true`) reasoned that
invariant mode was safe because `src/` contains no `CultureInfo`/`TimeZoneInfo` usage. That
reasoning addressed the wrong risk. `Microsoft.Data.SqlClient` itself depends on ICU when
opening a connection — independent of anything this service's own code does — and throws
`System.NotSupportedException: Globalization Invariant Mode is not supported` from
`SqlConnection.TryOpen` the moment `Program.cs`'s dev-time `MigrateAsync()` call tries to open
one. Plain chiseled forces invariant mode unconditionally (there is no override), so this was
undetectable by any unit or architecture test — it only surfaced once an actual container ran
against a real database, which is exactly what a container's own claims (research.md's own
methodology note) said to distrust until verified. The fix is `-extra` (+14.8 MB compressed,
restores ICU/tzdata) with no `DOTNET_SYSTEM_GLOBALIZATION_INVARIANT` override — the fallback
this document already named for "if a culture-dependent hazard ever surfaces", just triggered
by the database driver rather than by application code.

**Rationale**: The measured compressed sizes of the .NET 10 runtime bases are 91.4 MB for
full `noble`, 67.4 MB for `noble-chiseled-extra`, 52.6 MB for `noble-chiseled`, and 51.8 MB
for `alpine`. Chiseled additionally *already sets* `USER $APP_UID` in the image and ships no
package manager and no shell — the full `noble` and `alpine` images still run as root unless
you add `USER` yourself. Choosing chiseled therefore satisfies FR-002 by default rather than
by remembering, which is the shape Principle V asks for.

`InvariantGlobalization` turned out not to be a choice at all, in the opposite direction from
what this section originally argued: plain chiseled images force
`DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=true` unconditionally, and that forced invariant mode
breaks `Microsoft.Data.SqlClient`'s own connection-open path outright — a driver-level ICU
dependency this service's application code has no visibility into and could not have
disproven by grep, no matter how thoroughly. The original analysis (`src/` has no
`CultureInfo`/`TimeZoneInfo` usage; all timestamps are UTC) is still true, and still
irrelevant to why this failed. `-chiseled-extra` (+14.8 MB compressed) is the fix, exactly as
anticipated for "if a culture-dependent behaviour ever surfaces" — just surfaced by the data
access layer on the very first database connection, not by any code this service owns.

The consequence to plan around is that **a chiseled image has no shell and no `curl`**. Its
rootfs is `FROM scratch` plus six Ubuntu slices (`base-files`, `ca-certificates_data`,
`libc6_libs`, `libgcc-s1_libs`, `libssl3t64_libs`, `libstdc++6_libs`); the `app` user's shell
is literally `/bin/false`. The `-extra` variant does not help — it adds only ICU and tzdata.
A `docker-compose` `healthcheck:` runs *inside* the container, so it hits the same wall.
Microsoft ships no first-party probe utility; `dotnet/dotnet-docker#4300`, which proposes
one, is still open, and the maintainers' answer in discussion #4296 is to publish your own
binary and invoke it in JSON-array (exec) form, since without a shell you also cannot write
`|| exit 1`. A thirty-line console app is cheaper than a new third-party dependency and
cheaper than reverting to a shell-bearing base.

**Alternatives considered**:
- *Plain `chiseled` (52.6 MB compressed, no ICU/tzdata)*: the original choice, rejected after
  container testing (T014) showed `Microsoft.Data.SqlClient` cannot open a connection under
  the invariant globalization mode plain chiseled forces unconditionally — see the correction
  above. 14.8 MB cheaper, but non-functional for a service with a SQL Server dependency.
- *Full `noble` + install `curl`*: +39 MB, restores a shell and a package manager to the
  attack surface, needs an explicit `USER`, and `curl` is not even present by default — the
  official ASP.NET Core docs' own curl-based healthcheck example was reported broken for
  exactly this reason (`AspNetCore.Docs#24341`).
- *Alpine*: 0.8 MB smaller than chiseled but runs as root by default, and swaps glibc for
  musl, which changes the failure surface of `Microsoft.Data.SqlClient` for no benefit.
- *`-composite` chiseled* (52.0 MB, ReadyToRun-compiled framework): marginally smaller and
  faster to start, but pins the app to that exact framework version. Wrong trade for a slice
  whose deliverable is a *baseline* others will vary against.
- *No `HEALTHCHECK`, probe from the host instead*: fails FR-005, which requires the
  container's health status to be the existing readiness surface, and leaves Compose's
  `depends_on: condition: service_healthy` with nothing to wait on.
- *ReadyToRun for the app itself*: improves startup but increases image size and requires the
  build stage to pin the runtime identifier. Deliberately left out of the first baseline so
  there is something to compare against later.

---

## R2. SQL Server in the composed stack, and Apple Silicon

**Decision**: `mcr.microsoft.com/mssql/server:2022-latest` with `platform: linux/amd64`
pinned explicitly, `MSSQL_PID=Developer`, a named volume for data, and a
`sqlcmd`-based healthcheck that the API waits on via `depends_on: condition: service_healthy`.

**Rationale**: Microsoft states plainly that SQL Server container images are supported only
on x86-64 Linux hosts and that "emulation or translation environments (for example, Rosetta
2, Prism, or QEMU) aren't tested or supported"; the registry manifests for both
`2022-latest` and `2025-latest` are single-platform amd64, with no multi-arch index. So on an
Apple Silicon machine this container runs under emulation no matter what, and naming
`platform: linux/amd64` turns a confusing runtime warning into an explicit, documented
choice. 2022 rather than 2025 because SQL Server 2025 requires AVX, which Docker Desktop's
x86 emulation did not provide — RTM containers crashed on Apple Silicon and the fix landed
only in 2025 CU1. Choosing 2022 keeps a developer's first `docker compose up` off that
cliff. `azure-sql-edge`, the historical arm64 answer, is retired (end of support
2025-09-30) and is not an option.

`MSSQL_SA_PASSWORD` is the current variable; `SA_PASSWORD` is deprecated. The password must
be ≥8 characters drawn from three of the four character classes or the container exits at
startup — worth stating in `.env.example`, because the failure mode otherwise looks like a
broken stack rather than a rejected password.

`sqlcmd` lives at `/opt/mssql-tools18/bin/sqlcmd` in current images (the old
`/opt/mssql-tools/bin` path is gone), and tools18 encrypts by default, so a healthcheck
against the container's self-signed certificate needs `-C` to trust it. Both details are the
kind that turn into a twenty-minute debugging session if guessed.

**Alternatives considered**: 2025 CU1+ (viable, but asks every developer to be on a recent
Docker Desktop or OrbStack for AVX); Postgres or SQLite for local convenience (rejected — it
would mean the local stack no longer exercises the provider the service actually deploys
against, which defeats the purpose of the slice); a host-installed or shared remote SQL
instance (rejected — FR-004 requires a clean checkout to work with one command).

**Not verified**: whether the mssql image honours `MSSQL_SA_PASSWORD_FILE` pointing at a
Compose secret. It is widely reported but absent from Microsoft's documentation
(`microsoft/mssql-docker#672`), so the plan uses environment interpolation from an untracked
`.env`, which *is* documented. If the `_FILE` form is confirmed by test, it is a strictly
better mechanism and worth revisiting.

---

## R3. Applying migrations in the composed stack

**Decision**: the API container runs with `ASPNETCORE_ENVIRONMENT=Development`, reusing the
existing development-only `MigrateAsync()` call in `Program.cs`. No migration job, no
migration bundle, no new code path.

**Rationale**: `Program.cs` already migrates on startup in Development only, and already has
the machinery to report *not-yet-ready* on `/health/ready` while it does so (`StartupState`,
added in slice 003). The composed stack is a local development environment; running it as
Development is accurate rather than a shortcut, and it means this slice adds zero migration
machinery. Critically, the *image* is identical either way — environment is configuration, so
the artifact being size-baselined and secret-scanned is the same artifact a later slice
deploys. What Development does change is worth recording: OpenAPI is mapped at `/openapi`,
and first-run cold start includes migration time. Both are noted as measurement conditions in
the baseline (see [contracts/baseline-record.md](contracts/baseline-record.md)) rather than
left to surprise the next reader.

Microsoft's own guidance is to prefer a one-shot migration job over per-replica
auto-migration, and that guidance is right — for a deployed environment. It is also
explicitly a *deployment* concern, which FR-011 places outside this slice, and Principle X
forbids building capability for an anticipated need when a seam suffices. The seam here is
the existing environment check: the container that applies migrations is chosen by
configuration, not by code.

**Alternatives considered**: an `efbundle` one-shot service with
`depends_on: condition: service_completed_successfully` (the shape S6 should adopt; rejected
now as importing S6's concerns, and a framework-dependent bundle would additionally need a
runtime-bearing image, while a self-contained bundle on a chiseled base is untested — I could
find no Microsoft statement that it is supported); `dotnet ef database update` from the host
(breaks "one command"); a SQL script applied by an init container (needs a review process
this slice has no basis to define).

---

## R4. Graceful shutdown: the budget arithmetic

**Decision**: `HostOptions.ShutdownTimeout = 15s`, set explicitly in `Program.cs`; Compose
`stop_grace_period: 45s`; a draining readiness state that flips on
`ApplicationStopping`; exec-form `ENTRYPOINT`. The OTLP export timeout configured in slice
003 is left at 10 s.

**Rationale**: .NET handles SIGTERM out of the box — `ConsoleLifetime` registers a real POSIX
handler, `ApplicationStopping` fires, and Kestrel closes its listeners and stops taking new
requests while draining in-flight ones. The default `ShutdownTimeout` is 30 s; when it
expires, pending requests are *aborted forcefully*. Setting it explicitly to 15 s makes
FR-007's "documented finite grace period" a value in the codebase rather than an inherited
default nobody chose.

The trap is what happens *after* `StopAsync`. OpenTelemetry's providers are DI singletons,
disposed when the host's service provider is disposed, and each provider's `Dispose` calls
`Shutdown` with a **hardcoded 5000 ms**. With traces, metrics, and logs all registered, an
unreachable Collector can therefore add up to ~15 s *on top of* the shutdown timeout. So the
budget is 15 s of draining plus a ≤15 s flush tail, and Compose's grace period must exceed
their sum or Docker sends SIGKILL mid-flush and the exit stops being clean. 45 s covers it
with margin. Compose's default grace period is 10 s, which would have been shorter than the
drain alone — this is precisely the kind of silent mismatch the spec's US2 asks to be proven
rather than assumed.

`ENTRYPOINT` must be exec form. In shell form, `/bin/sh -c` becomes PID 1 and does not
forward SIGTERM, so the app never sees the signal and is SIGKILLed at the end of the grace
period — the whole of FR-007 would silently not hold. (A chiseled image has no shell, so
shell form would fail outright; the rule matters anyway because it must survive a future base
change.) No `tini`/`--init` is needed for a single-process .NET app.

The draining state needs writing because ASP.NET Core has no built-in one: `HealthStatus` has
exactly three values and none of them means "shutting down". The documented pattern is a
singleton health check that subscribes to `ApplicationStopping` and reports `Unhealthy` on the
*readiness* endpoint only, leaving liveness healthy so an orchestrator does not restart the
container mid-drain. This repository already has the right seam — `StartupState` plus
`StartupHealthCheck`, tagged `ready` — so this is an extension of an existing pair, not a new
mechanism.

**Alternatives considered**: lowering slice 003's OTLP export timeout from 10 s to ~3 s to
shrink the flush tail (rejected: it would rewrite a constant that slice reasoned about and
documented at length, to buy margin that a larger grace period buys for free); leaving
`ShutdownTimeout` at its 30 s default (rejected: FR-007 asks for a *documented* period, and a
default is not a decision); a `DelayedShutdownHostLifetime` that sleeps before propagating the
stop, as the official Kubernetes sample suggests for ingress propagation delay (correctly an
S6 concern — there is no ingress here).

**Not verified**: whether the process exit code changes when `ShutdownTimeout` expires. No
Microsoft documentation states one; the familiar 143/137 codes are container-runtime
semantics, not .NET's. The 5000 ms OpenTelemetry dispose timeout is verified from SDK source,
not documentation, and could change between versions — which is another argument for margin
in the grace period rather than a tight calculation.

**Correction, found only by driving a real SIGTERM against a running container (edge case 3
— a signal arriving before readiness)**: `ConsoleLifetime` does not install its SIGTERM
handler until `app.Run()`/`RunAsync()` actually starts the host, so a signal arriving during
the pre-`Run()` dev-time `MigrateAsync()` call (Program.cs) — e.g. because the database
container is down and the connection is retrying — had no handler at all and the OS's default
disposition hard-killed the process (`docker stop` returned in well under a second, exit
143, zero log output, with a database container deliberately stopped to force the retry
window). The fix is a `PosixSignalRegistration` for `SIGTERM`, created immediately after
`app.Build()`, whose token cancels the migration call. The first attempt at this fix *still*
produced exit 143: `PosixSignalContext.Cancel` defaults to `false`, so the runtime's own
default terminate-the-process action runs after a handler returns unless the handler sets
`context.Cancel = true` explicitly — an easy-to-miss inversion (registering a handler at all
does *not* by itself suppress the default action). With `context.Cancel = true` set, the
container now exits 0 in this path, confirmed by the same repro.

## R5. HTTPS redirection inside the container

**Decision**: stop calling `app.UseHttpsRedirection()` when TLS is terminated upstream,
gating it on configuration rather than deleting it. The container listens on plain HTTP 8080
only, inherited from the base image's `ASPNETCORE_HTTP_PORTS=8080`; `ASPNETCORE_URLS` is not
set anywhere.

**Rationale**: With no HTTPS port discoverable, the middleware today does not redirect at
all — it logs "Failed to determine the https port for redirect" once and serves the request.
So the *current* behaviour in a container is a warning, not a fault. The hazard is
conditional and nasty: if an HTTPS port ever becomes discoverable (an inherited
`ASPNETCORE_HTTPS_PORT`, or an `https://` entry in `ASPNETCORE_URLS`), every plain-HTTP
request gets a 307 — including `GET /health/ready`, at which point the health probe stops
reporting application health and starts reporting the redirect. Behind a TLS-terminating
ingress the middleware also needs `UseForwardedHeaders()` ahead of it or it sees `http` for
already-encrypted traffic and redirect-loops. Since S6 puts Front Door and APIM in front of
this service, in-app redirection is the wrong layer for it permanently, and a booby-trapped
no-op is worse than an explicit absence.

`ASPNETCORE_HTTP_PORTS=8080` is the current documented mechanism and is already set by
`runtime-deps:10.0` (which also sets `APP_UID=1654` and `DOTNET_RUNNING_IN_CONTAINER=true`);
Microsoft removed `ASPNETCORE_URLS=http://+:80` from the images in .NET 8 so a non-root user
can bind. `ASPNETCORE_URLS` takes precedence over `ASPNETCORE_HTTP_PORTS`, so setting it in
`compose.yaml` would silently disable the image default — hence the rule to leave it unset.
`DOTNET_GENERATE_ASPNET_CERTIFICATE=false` is set so no development certificate is ever
created in an image, which Microsoft warns can lead to spoofing and privilege elevation.

**Alternatives considered**: keeping the call and relying on it being a no-op (rejected —
correctness by coincidence, and it depends on an environment variable *not* being set);
deleting the call outright (rejected — it is still correct for the `dotnet run` HTTPS
workflow, which does have a port); setting `HttpsRedirectionOptions.HttpsPort` explicitly
(wrong direction: it would *enable* redirection in a container that cannot serve HTTPS).

**Not verified**: no single Microsoft sentence says "do not call `UseHttpsRedirection` in a
container". The conclusion is assembled from the port-resolution, reverse-proxy, and Web-API
sections of the HTTPS-enforcement documentation, all of which point the same way.

---

## R6. Image secret scanning, the negative proof, and the baseline

**Decision**: Trivy — `trivy image --scanners secret --image-config-scanners secret
--severity HIGH,CRITICAL --exit-code 1` — with a separate `Dockerfile.secretbait` that copies
a freshly generated throwaway RSA private key to `/app/config/leak.pem`, and a scan script
that fails if the release-candidate image produces any finding **or** if the bait image
produces none.

**Rationale**: Trivy is Apache-2.0, a single binary, needs no account, and does secret
scanning as pure regex, so `--scanners secret` requires no vulnerability-database download
and works offline. Its `--exit-code` is generic across scanners, so surviving secret findings
fail the command directly, and `--image-config-scanners secret` extends the scan to the image
*config and history* — which is where a secret passed as a build `ENV` or baked into a `RUN`
line hides, and exactly the kind of leak FR-008's "runtime default configuration" clause
means. False positives have three documented escape hatches (`.trivyignore`, path-scoped
`.trivyignore.yaml`, and a custom `trivy-secret.yaml` with allow-rules), so a finding never
has to be handled by disabling the gate.

The negative proof needs care, and this is the single most useful thing the research turned
up. Trivy ships a built-in **allow** rule `examples` matching `(?i)example`, plus `tests`
matching any path containing `test`, plus `markdown`, `vendor`, and `/usr/{share,include,lib}`.
So the canonical AWS dummy key `AKIAIOSFODNN7EXAMPLE` is silently allow-listed, and any bait
placed at a path containing "test" is skipped. A naive negative test therefore *passes* and
delivers precisely the false confidence FR-009 exists to prevent. Generating a real
throwaway RSA key and copying it to `/app/config/leak.pem` fires the built-in `private-key`
rule (HIGH) with no allow-rule collision and no risk of committing a real credential — the
key is generated at scan time and never tracked. A second bait case sets an
`AWS_ACCESS_KEY_ID` in `ENV` to exercise the image-config scanner too, using a synthetic
value that avoids the word "example".

**Vulnerability scanning** (FR-012) reuses the same tool for a different scanner: `trivy image
--scanners vuln --severity HIGH,CRITICAL --exit-code 1` against the release-candidate image,
in a separate script so a secret finding and a CVE finding are never conflated in one exit
code. The severity threshold is fixed at HIGH/CRITICAL rather than made configurable —
configurability is the vulnerability-*policy* question (waiver process, exception review)
that the spec's Out of Scope explicitly defers to S7's CI work; this slice only needs the
scan to run and report against one fixed bar every time. The chiseled base's near-empty
package set (research.md R1) is expected to keep this scan close to zero findings by
construction, which is itself evidence the base-image choice was right, not a reason to skip
running it.

For the baseline, the size question has a real trap: `docker images` SIZE and `docker image
inspect .Size` report **uncompressed** bytes, while a registry manifest reports **compressed**
layer sizes — which is what "pull cost" means and what SC-004 should record. Without pushing,
the accurate route is `docker buildx build --output type=oci,dest=img.tar` and summing the
layer sizes from the manifest; `docker save | gzip | wc -c` is a usable approximation but
compresses across layer boundaries and includes metadata, so it does not equal the manifest
sum. The baseline records both numbers with the command that produced each.

Cold start is measured by polling `/health/ready` from container start until 200, with the
image already built locally so no pull time is included, explicit `--cpus`/`--memory` limits
so the number reflects the app and not the host's spare capacity, the database already
healthy (stated, because "full stack from nothing" is a different metric and both are worth
publishing), the first run discarded as warm-up, and **median and p90 over ten runs** rather
than a mean — start-up distributions are right-skewed by JIT, GC, and disk outliers, so a mean
is the one summary statistic guaranteed to mislead.

**Alternatives considered**: TruffleHog (better layer coverage — it scans each layer tar
independently plus build history, so it catches a secret added in one layer and deleted in a
later one, which Trivy's merged-filesystem walk misses; rejected as the primary gate because
it is AGPL-3.0 and its verification step makes outbound network calls, but it is the right
tool for a deeper one-off audit); Gitleaks (MIT and offline, but has no image support — it
would need `docker export` into a directory first, which flattens layers anyway); `docker
scout` (no secret scanning, and account-backed); Syft/Grype (no secret scanning at all — the
cataloger was removed before v1.0).

**Not verified**: Trivy's own documentation does not state its whiteout/merged-filesystem
behaviour for secret scanning; the "walks the tree rooted at `/`" wording implies a secret
deleted in a later layer is missed, but this should be confirmed empirically with a
two-stage bait (`COPY` then `RUN rm`) before the scan's coverage is described to anyone. That
empirical check belongs in this slice's tasks, not in a footnote.
