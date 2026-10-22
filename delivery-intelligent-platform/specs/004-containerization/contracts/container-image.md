# Contract: Tenancy Service Container Image

**Spec**: [../spec.md](../spec.md) · **Plan**: [../plan.md](../plan.md) · **Research**: [../research.md](../research.md)

The image is this slice's deliverable and S6's deployable unit. This is what a consumer —
Compose today, a Kubernetes pod later — may rely on.

## Identity

| Property | Value |
|---|---|
| Build stages | `mcr.microsoft.com/dotnet/sdk:10.0` (restore, publish) → `mcr.microsoft.com/dotnet/aspnet:10.0-noble-chiseled-extra` (runtime) |
| Contents | the published `Tenancy.Api` output and the `Tenancy.HealthProbe` output. No SDK, no source, no shell, no package manager |
| Local tag convention | `tenancy-api:local` for development; `tenancy-api:rc` for the release-candidate build that is scanned and baselined |
| Platforms | `linux/amd64` and `linux/arm64` |

## Process

| Property | Value | Why it is in the contract |
|---|---|---|
| Effective user | uid `1654`, gid `1654` (`app`) | FR-002. Already `USER $APP_UID` in the chiseled base; set explicitly in the Dockerfile so a base-image change cannot silently reintroduce root |
| `ENTRYPOINT` | exec form, JSON array | Shell form would make `/bin/sh` PID 1, which does not forward SIGTERM — FR-007 would silently not hold (research.md R4) |
| Listening port | `8080`, plain HTTP | Inherited `ASPNETCORE_HTTP_PORTS` from the base image. Consumers must not set `ASPNETCORE_URLS`; it takes precedence and would override this |
| TLS | none in-process | Terminated upstream from S6 onward. No development certificate is generated (`DOTNET_GENERATE_ASPNET_CERTIFICATE=false`) |
| Root filesystem | may be mounted read-only | FR-002 |
| Required writable mount | `tmpfs` at `/tmp` | The runtime needs it for the diagnostics socket and temp-file APIs |
| Host privileges | none | No capabilities added, no privileged mode, no host networking |

### Data Protection

The ASP.NET Core Data Protection key ring has no persistent location in this image, so the
framework logs a warning ("Storing keys in a directory that may not be persisted outside of
the container") and uses ephemeral keys. This is **acceptable for this service**: it
authenticates bearer tokens issued by Entra ID and uses no auth cookies and no antiforgery
tokens, so nothing it protects needs to survive a restart. A consumer that later adds
cookie-based authentication must mount a persistent key location or configure an external
provider — recording it here so that change is a decision rather than a discovery.

## Signals

| Signal | Behaviour |
|---|---|
| `SIGTERM` | Kestrel closes its listeners and stops accepting new requests; in-flight requests drain; readiness flips to draining (see below); the process exits cleanly |
| Drain budget | `HostOptions.ShutdownTimeout` = **15 s**, configured explicitly. In-flight requests still running at expiry are aborted |
| Flush tail | Up to ~5 s per OpenTelemetry provider **after** the drain completes, if the collector is unreachable — so a consumer's kill grace period must be **≥ 45 s** to guarantee a clean exit (research.md R4) |
| `SIGKILL` | Not survivable by design. A consumer that sends it before the grace period elapses breaks FR-007's guarantee, not the image's |

## Health

| Endpoint | Purpose | Consumer |
|---|---|---|
| `GET /health/live` | Process liveness. Depends on no dependency, and stays `Healthy` while draining so a consumer does not restart a container mid-shutdown | liveness probe |
| `GET /health/ready` | Readiness. `Unhealthy` (503) while starting, while SQL Server is unreachable, and while draining — with a body that distinguishes the three for a human | readiness probe, Compose `service_healthy`, the image's own `HEALTHCHECK` |

Both are anonymous, as established by slice 003's `contracts/health-endpoints.md`.

The `HEALTHCHECK` is declared in the image, in exec form, invoking `Tenancy.HealthProbe`
against `http://localhost:8080/health/ready`. A chiseled image has no shell and no `curl`, so
neither a shell-form `HEALTHCHECK` nor a `curl`-based Compose healthcheck is possible
(research.md R1).

### `Tenancy.HealthProbe` contract

| Aspect | Value |
|---|---|
| Invocation | `["dotnet", "/app/probe/Tenancy.HealthProbe.dll", "http://localhost:8080/health/ready"]` |
| Exit `0` | response status is 200 |
| Exit `1` | any other status, a connection failure, or a timeout |
| Timeout | 2 s, well inside the `HEALTHCHECK` `--timeout` |
| Output | none on success; one line to stderr on failure, so `docker inspect`'s health log is useful |
| Dependencies | `HttpClient` only. No configuration, no logging, no telemetry — it must not be able to fail for a reason unrelated to the endpoint |

## Configuration inputs

Read via the existing `IConfiguration` keys. Environment variables use `__` as the section
separator. This slice adds **no new configuration key**.

| Variable | Required | Notes |
|---|---|---|
| `ConnectionStrings__TenancyDb` | yes | Secret-bearing. Never baked into the image |
| `AzureAd__Instance`, `AzureAd__TenantId`, `AzureAd__ClientId`, `AzureAd__Audience` | for authenticated requests | Not secrets, but not tracked either |
| `Observability__OtlpEndpoint` | no | Unset falls back to the SDK default (`localhost:4317`), which is *wrong inside a container* — the local stack sets it to the collector service |
| `Observability__NewRelicApiKey` | no | Secret. Unset locally; from Key Vault once deployed |
| `ASPNETCORE_ENVIRONMENT` | no | Defaults to Production. The local stack sets `Development`, which is also what applies migrations (research.md R3) |

## Secret guarantees

- No image layer contains a secret, credential, access token, or connection-string value.
- No image **config** entry (`ENV`, build args recorded in history, `LABEL`) contains one
  either — this is a separate scan surface and is scanned separately.
- `.dockerignore` excludes `.env`, `.env.*`, `**/appsettings.Development.json`, `**/bin`,
  `**/obj`, `.git`, and user-secrets paths, so a secret cannot enter the build context at all.
- Verified by `infrastructure/scripts/scan-image-secrets.sh`, which fails on any finding in
  the release-candidate image and *also* fails if it finds nothing in the deliberately baited
  image (FR-009).

## Vulnerability guarantee

- The release-candidate image MUST report zero unresolved HIGH or CRITICAL vulnerability
  findings, verified by `infrastructure/scripts/scan-image-vulnerabilities.sh`
  (`trivy image --scanners vuln --severity HIGH,CRITICAL --exit-code 1`), a fixed threshold
  applied every run (FR-012). This is a separate script and a separate exit code from the
  secret scan, so the two failure modes are never conflated.

## Verification a consumer can perform

```bash
# non-root, without needing a shell in the image
docker inspect --format '{{.Config.User}}' tenancy-api:rc   # -> 1654
docker top <container>                                       # -> UID 1654, never root

# clean SIGTERM within the grace period
time docker stop --timeout 45 <container>; docker inspect --format '{{.State.ExitCode}}' <container>

# health, from outside the container
curl -fsS http://localhost:8080/health/live
curl -isS http://localhost:8080/health/ready
```

`docker exec <container> id` does **not** work — there is no shell and no `id` binary. That is
the intended trade-off, and it is why `docker top` is the documented check.
