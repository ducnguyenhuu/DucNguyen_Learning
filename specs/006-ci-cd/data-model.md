# Data Model: CI/CD Pipeline with Performance Verification

**Branch**: `006-ci-cd` | **Date**: 2026-09-29

This slice adds no application tables. The spec's four entities are records the pipeline
**produces**; this document states where each one lives, how long it survives, and which one is
the authoritative evidence for a requirement.

## §1 — Entities and where they live

| Entity (spec) | Stored in | Identity | Retention | Authoritative for |
|---|---|---|---|---|
| **Pipeline Run** | GitHub Actions run | `run_id` + `head_sha` | GitHub default (90 days for logs) | SC-001 timing (run duration) |
| **Stage** | GitHub Actions job within the run | job name (stable — see `contracts/pipeline.md`) | same as run | FR-001 stage sequence; SC-005 failure identification |
| **Approval Record** | GitHub deployment + deployment review on environment `production` | deployment ID | Permanent in repository deployment history | FR-010, SC-003 |
| **Load-Test Result** | k6 `--summary-export` JSON, uploaded as a run artifact; summary rendered into the job summary | `run_id` | Artifact: 90 days. **Copied permanently** into `docs/operations/load-test-baseline.md` when used as verification evidence | SC-004 / spec 001 SC-003 |

GitHub's 90-day retention is acceptable for everything except the SC-003 verification, which must
outlive the run that produced it — hence the copy into `docs/`.

## §2 — Pipeline Run lifecycle

```text
queued ──► in_progress ──┬──► success
                         ├──► failure            (a gate failed; later jobs never start)
                         ├──► cancelled          (superseded by a newer commit — R9 —
                         │                        reason written to the job summary)
                         └──► waiting            (production job only, awaiting review)
                                  │
                                  ├──► approved ──► success | failure (expired > 7 days — R12)
                                  └──► rejected ──► failure
```

A run that reaches `deploy-dev` and fails leaves dev on the previous release (single revision mode keeps the previous revision serving,
plus spec 005 FR-014's zero-downtime rollout). There is no state in which dev is half-deployed.

## §3 — Approval Record fields

Recorded by GitHub on the deployment review; the pipeline adds nothing it could forge.

| Field | Source |
|---|---|
| Approver identity | GitHub user who reviewed |
| Outcome | approved / rejected |
| Timestamp | review time |
| Change | `head_sha` of the run, commit author, commit message |
| Target environment | `production` |

The `production` job additionally writes these into its job summary as the human-readable
"would-deploy" record.

## §4 — Load-Test Result fields

Extracted from the k6 summary into the job summary and the baseline document.

| Field | Meaning | Gate |
|---|---|---|
| `p50`, `p95`, `p99` (ms) | `http_req_duration` for `phase:steady, kind:tenant-read` | p95 < 1000 |
| `error_rate` | `http_req_failed` rate in the steady phase | < 0.01 |
| `vus` | concurrent virtual users (50) | — |
| `tenants` | distinct tenants exercised (20) | — |
| `requests` | steady-phase sample size | reported, no threshold |
| `identity_count` | distinct caller identities (1 — see research R7 limitation) | reported, no threshold |
| `commit` | `head_sha` deployed at measurement time | — |
| `timestamp` | measurement start (UTC) | — |

## §5 — Identity model additions (ADR-022)

| Identity | Kind | Lives in | Can do |
|---|---|---|---|
| `id-github-deployer` | user-assigned managed identity, GitHub-federated | `infrastructure/terraform/persistent/` | Push to ACR; update the container app's image only. **Not** a tenant member. |
| `id-loadtest-client` | user-assigned managed identity, GitHub-federated | same | Call the Tenancy API with app role `Tenancy.Automation.Member`. **No** Azure RBAC. |

Inside the Tenancy API, `id-loadtest-client` becomes a `User` row via the existing
just-in-time provisioning (`tid` + `oid`, email fallback `{oid}@unresolved.invalid`) and a
`Membership` row in each `loadtest-NN` tenant it creates. No schema change is required.
