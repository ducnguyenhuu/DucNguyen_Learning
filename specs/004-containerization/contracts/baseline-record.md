# Contract: Image Size and Cold-Start Baseline Record

**Spec**: [../spec.md](../spec.md) · **Research**: [../research.md](../research.md)

FR-010 and SC-004 require a recorded baseline that another developer can repeat. This is the
required field set for `docs/operations/container-image-baseline.md`. A field with no value
is a defect in the record, not an omission — the whole point is that the numbers are
comparable later.

## Identification

| Field | How it is obtained |
|---|---|
| Revision | `git rev-parse HEAD` — the commit the image was built from |
| Working tree state | clean or dirty; a dirty tree makes the record unrepeatable, so say so |
| Image tag and **digest** | `docker image inspect --format '{{.Id}}' tenancy-api:rc`. The digest matters because the same tag rebuilt is different bytes |
| Base image | tag **and** digest of `aspnet:10.0-noble-chiseled-extra` at build time |
| Date measured | — |

## Size

Both numbers, each with the command that produced it. They differ by roughly two to four
times, so a size without a method is meaningless.

| Field | Command |
|---|---|
| Uncompressed | `docker image inspect --format '{{.Size}}' tenancy-api:rc` |
| Compressed (accurate) | `docker buildx build --output type=oci,dest=img.tar .` then sum the layer `size` values from the manifest referenced by `index.json` |
| Compressed (approximate) | `docker save tenancy-api:rc \| gzip -9 -c \| wc -c` — record it as an approximation; it compresses across layer boundaries and includes metadata, so it does not equal the manifest sum |
| Largest layers | `docker history --no-trunc tenancy-api:rc` — the useful part of the record, because it is what a future size regression is diagnosed from |

## Cold start to ready

| Field | Notes |
|---|---|
| Definition | wall-clock time from `docker run` to the first `200` from `GET /health/ready` |
| Repetitions | ≥10 |
| Warm-up | the first run is discarded, and the record says so |
| Statistics | **median and p90**. Not a mean — startup distributions are right-skewed by JIT, GC, and disk outliers |
| Poll interval | recorded, since it bounds resolution and biases the result upward by roughly half an interval |

## Conditions (all required)

| Field | Why it must be recorded |
|---|---|
| Host CPU model, core count, RAM, disk type, OS version | the dominant term in every number here |
| Docker/Compose version, and Docker Desktop VM CPU/RAM allocation | on macOS and Windows the VM is an extra opaque cache and scheduling layer |
| Architecture and whether emulation was involved | SQL Server runs emulated on Apple Silicon |
| `--cpus` and `--memory` limits used | without explicit limits the measurement reflects the host's spare capacity, not the app |
| Whether the image was already built locally | pull time must never be included |
| **Whether the database was already healthy** | "API container alone, database healthy" and "whole stack from nothing" are different metrics. Record the first as the headline and the second alongside it, since SC-001's 3-minute criterion is about the second |
| Whether migrations ran during the measured start | the composed stack runs as `Development`, so first start against an empty volume includes migration time |
| `ASPNETCORE_ENVIRONMENT` | it changes what happens during startup |
| Machine on battery / thermally throttled | a quietly invalidating condition |

## Repeatability statement

The record ends with the exact commands to reproduce it, in order, such that a developer on
the same revision can run them and compare. `infrastructure/scripts/measure-image-baseline.sh`
produces the numbers; the document is written from its output and adds the conditions the
script cannot know.
