# Quickstart: Containerization

**Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md) · **Research**: [research.md](research.md)

Every section below maps to a requirement, and every check is one a reviewer can run. If a
check cannot be run, the requirement is not done — that is the whole shape of this slice.

## Prerequisites

| Requirement | Notes |
|---|---|
| Docker Desktop or OrbStack | Compose v2. On Apple Silicon, SQL Server runs under x86 emulation — give the VM at least 4 GB and expect a slow first start (research.md R2) |
| Trivy | `brew install trivy`. Needed only for the secret scan |
| .NET 10 SDK | Not needed to run the stack — the image builds it. Needed for `dotnet run`, tests, and `dotnet ef` |
| An `.env` file | `cp .env.example .env`, then fill it in. Nothing works without it, by design |

No New Relic account is needed; the collector stays the local default.

## 1. Start the stack (FR-003, FR-004, SC-001)

```bash
cp .env.example .env      # then edit: MSSQL_SA_PASSWORD and the AzureAd values
docker compose up --build --wait
```

`--wait` returns only once every service with a healthcheck is healthy. Then:

```bash
curl -fsS http://localhost:8080/health/live      # 200
curl -isS http://localhost:8080/health/ready     # 200 once migrations have finished
```

Sign in and perform an existing tenant operation (for example `GET /tenants`, then a rename)
with a bearer token from the Entra app registration, exactly as in slice 001's quickstart.
The operation must succeed, and the collector's console output must show its trace.

For SC-001, repeat from a clean state three times and confirm each reaches a ready,
signed-in-able service within 3 minutes:

```bash
docker compose down -v && time docker compose up --build --wait
```

Note `-v`: it drops the database volume, so this is a genuine clean-checkout timing including
migrations. Without `-v` you are measuring a warm start.

### Prove the missing-prerequisite path (FR-008, edge case 2)

```bash
unset MSSQL_SA_PASSWORD; mv .env .env.bak
docker compose up          # must fail immediately, naming the missing variable
mv .env.bak .env
```

The failure must name the variable and must **not** fall back to a default password.

## 2. Prove the service survives a collector outage (FR-006, SC-005)

```bash
docker compose stop otel-collector
curl -isS http://localhost:8080/health/ready     # still 200
# perform an authenticated tenant operation      # still succeeds
docker compose start otel-collector
```

Also worth doing the harder version: `docker compose down` and bring the stack up with the
collector already stopped, confirming the service still reaches ready (edge case 4).

## 3. Prove the container is not root (FR-002, SC-002)

```bash
docker inspect --format '{{.Config.User}}' tenancy-api:local     # -> 1654
docker top $(docker compose ps -q api)                            # -> UID 1654, never root
```

`docker exec ... id` will not work — the chiseled image has no shell and no `id` binary. That
is intentional, and `docker top` reads the host's process table, so it is the stronger check
anyway.

Also confirm the read-only root filesystem is real:

```bash
docker inspect --format '{{.HostConfig.ReadonlyRootfs}}' $(docker compose ps -q api)   # true
```

## 4. Prove clean shutdown while a request is in flight (FR-007, SC-002)

```bash
# start a slow-ish authenticated request in one shell, then in another:
time docker compose stop api
docker inspect --format '{{.State.ExitCode}}' $(docker compose ps -aq api)
```

Expected: the in-flight request completes or is cancelled safely, `stop` returns well inside
the 45 s grace period, and the exit code reflects a clean stop rather than a SIGKILL. Then
confirm nothing was lost: the mutation the request acknowledged is present in the database
**and** so is its audit entry.

### The draining state

```bash
# during shutdown, from a third shell:
curl -isS http://localhost:8080/health/ready     # 503, body says "shutting down"
curl -isS http://localhost:8080/health/live      # still 200 — a draining container is not dead
```

### Termination before readiness (edge case 3)

```bash
docker compose up -d --build api & sleep 1; docker compose stop api
```

The container must exit cleanly and must never have returned 200 from `/health/ready`.

## 5. Prove the image contains no secret — and that the scan can fail (FR-008, FR-009, SC-003)

```bash
./infrastructure/scripts/scan-image-secrets.sh tenancy-api:rc
```

The script does two things, and the second is the one that matters:

1. Scans the release-candidate image, including its **config and history**, and fails on any
   finding.
2. Builds `Dockerfile.secretbait` — which copies a freshly generated throwaway RSA private key
   to `/app/config/leak.pem` and sets a synthetic `AWS_ACCESS_KEY_ID` in `ENV` — and **fails
   if the scan reports nothing**.

Read research.md R6 before changing the bait. Trivy ships built-in *allow* rules for anything
matching `example` or any path containing `test`, so the canonical `AKIAIOSFODNN7EXAMPLE`
dummy key and any bait file named `*test*` are silently ignored — a negative test built from
either passes while proving nothing.

Confirm by hand once, too, since a script that checks itself is worth distrusting:

```bash
trivy image --scanners secret --image-config-scanners secret tenancy-api:rc     # no findings
trivy image --scanners secret --image-config-scanners secret tenancy-api:bait   # findings
```

## 6. Record the baseline (FR-010, SC-004)

```bash
./infrastructure/scripts/measure-image-baseline.sh tenancy-api:rc
```

It reports uncompressed size, compressed size (from an OCI export, plus the `docker save |
gzip` approximation), the largest layers, and cold-start-to-ready as median and p90 over ten
runs with the first discarded. Then write
`docs/operations/container-image-baseline.md` from that output, adding the conditions the
script cannot know — host specification, Docker VM allocation, emulation, battery state — per
[contracts/baseline-record.md](contracts/baseline-record.md).

Verify the record is actually repeatable by having the numbers reproduced from the same
revision. If they cannot be, the missing field is a condition that was not written down.

## 7. Confirm nothing from slice 003 regressed

```bash
dotnet test
```

Unit, integration, architecture, and tenant-isolation tests all still pass — including the new
draining-readiness tests and the tracked-configuration gate that fails if a credential literal
or a root `USER` appears in container configuration.

## 8. The `dotnet run` workflow still works

Containerization must not become the only way to run the service:

```bash
docker compose -f deploy/otel-collector/docker-compose.yml up -d
dotnet run --project src/Tenancy/Tenancy.Api
```

Configuration still comes from .NET User Secrets here, not `.env` — user secrets are not
visible inside a container, which is why the composed stack uses environment variables
instead. Both paths are supported; neither is the other's fallback.

## What is deliberately absent

No registry push, no Kubernetes manifest, no Helm chart, no pipeline. The scan and baseline
scripts each exit non-zero on failure specifically so S7 can wire them into CI as a step
rather than a rewrite. `deployment/kubernetes/` and `deployment/helm/` stay empty until S6.
