# Container Image Baseline: `tenancy-api`

**Spec**: [specs/004-containerization/spec.md](../../specs/004-containerization/spec.md) ·
**Contract**: [specs/004-containerization/contracts/baseline-record.md](../../specs/004-containerization/contracts/baseline-record.md)

FR-010/SC-004's recorded baseline, produced by
`infrastructure/scripts/measure-image-baseline.sh tenancy-api:rc 5` (see repeatability
statement below for the exact commands). This is the **first** baseline for this slice —
there is nothing yet to compare it against; that is the point of recording it.

## Identification

| Field | Value |
|---|---|
| Revision | `724581e9de7720497d51f2f658e0a0f27b1294be` |
| Working tree state | **Dirty** — this run measured the 004-containerization slice mid-implementation, before the branch's changes were committed. Re-run after commit for a citable record; the numbers below are not invalidated by an uncommitted tree, but the revision above cannot be checked out standalone yet |
| Image ID | `sha256:c4f7e177f323ee02c77c405252bac00f6339651b943e9783d307a86ecd046ced` |
| Base image | `mcr.microsoft.com/dotnet/aspnet:10.0-noble-chiseled-extra@sha256:6385dc0eaef704fad88d3f65c334e791a371bbe448f52ca39d83d2df49251e28` |
| Date measured | 2026-09-25 |

## Size

| Field | Value | Command |
|---|---|---|
| Uncompressed | 69,149,703 bytes (≈65.9 MiB) | `docker image inspect --format '{{.Size}}' tenancy-api:rc` |
| Compressed (approximate) | 84,350,590 bytes (≈80.4 MiB) | `docker save tenancy-api:rc \| gzip -9 -c \| wc -c` |
| Compressed (accurate) | not captured this run — the OCI export tarball was inspected only for its existence, not summed; re-run and sum `index.json`'s manifest layer sizes for the citable number | `docker buildx build --output type=oci,dest=img.tar .` |

**Largest layers** (`docker history --no-trunc tenancy-api:rc`):

| Layer | Size |
|---|---|
| `COPY /rootfs /` (base image rootfs) | 54.0 MB |
| `COPY /usr/share/dotnet /usr/share/dotnet` (base image runtime) | 89.2 MB* |
| `COPY /dotnet /usr/share/dotnet` (ICU/tzdata, `-extra` variant) | 30.3 MB |
| `COPY /app/publish ./` (this service's published output) | 55.4 MB |
| `COPY /app/probe ./probe/` (`Tenancy.HealthProbe`) | 119 kB |

\* Base-image layer sizes shown by `docker history` are **uncompressed**; they do not sum
directly to the compressed totals above.

## Cold start to ready

**Definition**: wall-clock time from `docker run` to the first `200` from `GET /health/ready`,
API container alone, **database already healthy** (this is the headline metric per
contracts/baseline-record.md — "whole stack from nothing" is a different number, not yet
recorded).

| Field | Value |
|---|---|
| Repetitions | 5 (first discarded as warm-up) |
| Raw runs (post-warm-up) | 0.788s, 0.773s, 0.785s, 0.788s |
| Median | 0.788s |
| p90 | 0.788s |
| Poll interval | 0.2s (biases the result upward by up to ~0.2s) |

Only 4 post-warm-up runs were measured (5 total, 1 discarded), fewer than
contracts/baseline-record.md's "≥10" recommendation — re-run with a larger count for a fully
citable record; these numbers establish the baseline exists and is of the right order of
magnitude, not a final statistically robust figure.

## Conditions

| Field | Value |
|---|---|
| Host | Apple M3 Pro, 11 cores, 18 GiB RAM, macOS 26.5.2 |
| Architecture / emulation | `linux/arm64`, native — no emulation for this image (SQL Server itself runs emulated `linux/amd64` on this host per research.md R2, but that is not what is timed here) |
| Docker | Docker Desktop 29.3.1, BuildKit v0.28.1 |
| `--cpus`/`--memory` limits | none set — this run reflects the host's spare capacity, not a constrained budget. A future baseline should pin both |
| Image already built locally | yes — no pull time included |
| Database already healthy | yes — `sqlserver` from `compose.yaml`, started and confirmed healthy before timing began; the API container joined its network directly rather than through `compose.yaml` |
| Migrations ran during measurement | yes, each run — the volume was freshly created (`docker compose down -v`) once before the first (discarded) run, so run 1 includes first-ever migration; whether runs 2–5 re-ran a no-op migration against an already-migrated schema was not isolated in this pass |
| `ASPNETCORE_ENVIRONMENT` | `Development` |
| Battery / thermal state | Plugged in, not thermally throttled |

## Repeatability statement

```bash
# 1. Bring up the database dependency only, and wait for it to be healthy
cp .env.example .env   # fill in MSSQL_SA_PASSWORD
docker compose up --wait sqlserver

# 2. Build the release-candidate image
docker build -t tenancy-api:rc .

# 3. Run the baseline script (requires step 1's sqlserver container to still be running)
./infrastructure/scripts/measure-image-baseline.sh tenancy-api:rc 10
```

Re-run against a committed revision, with `--cpus`/`--memory` limits pinned and at least 10
post-warm-up runs, for a citable comparison baseline.
