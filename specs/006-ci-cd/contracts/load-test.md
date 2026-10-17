# Load-Test Contract

**Branch**: `006-ci-cd` | **Date**: 2026-09-29
**Verifies**: spec 001 SC-003 — 95% of tenant reads under 1 s at 50 concurrent users across 20 tenants.

## Target

The deployed dev environment through its **public path**: `https://<FRONTDOOR_ENDPOINT>` → APIM →
Container Apps → Azure SQL. Never the container app directly — SC-003 is about what a user experiences.

## Authentication

The `load-test` job logs in as `id-loadtest-client` (OIDC) and requests a token for the API
audience:

```bash
TOKEN=$(az account get-access-token --resource "$TENANCY_API_APP_ID_URI" --query accessToken -o tsv)
```

The token carries `roles: ["Tenancy.Automation.Member"]` (ADR-022). It is passed to k6 as an
environment variable, never written to disk or logged, and is valid far longer than the ~4-minute run.

## Seeding (`tests/load/seed.sh`)

Idempotent; safe to run on every pipeline:

1. `GET /tenants` — list tenants the automation identity belongs to.
2. For each missing name in `loadtest-01` … `loadtest-20`: `POST /tenants` with an
   `Idempotency-Key` derived from the name, so a retried seed never creates duplicates.
3. Write the 20 tenant IDs to a file k6 reads.

The automation identity becomes administrator of those 20 tenants by creating them, and of nothing
else.

## Scenario (`tests/load/tenant-reads.js`)

| Phase | Executor | VUs | Duration | Measured? |
|---|---|---|---|---|
| `warmup` | `constant-vus` | 50 | 30 s | No — tagged `phase:warmup` |
| `steady` | `constant-vus` | 50 | 2 min | Yes — tagged `phase:steady` |

Each iteration, virtual user *n* selects tenant `n mod 20` and issues, tagged `kind:tenant-read`:
- `GET /tenants/{tenantId}`
- `GET /tenants/{tenantId}/members`

These are the tenant-scoped read operations spec 001 defines. Think time: 1 s between iterations.

## Thresholds (the gate)

```js
thresholds: {
  'http_req_duration{phase:steady,kind:tenant-read}': ['p(95)<1000'],
  'http_req_failed{phase:steady}': ['rate<0.01'],
}
```

A breach makes k6 exit non-zero, which fails the `load-test` job. There is **no automatic retry**
of a failed run: a breach is either a real regression or real flakiness, and both need a human to
look. The job summary names the breached metric and its measured value.

## Output

- `k6-summary.json` (`--summary-export`) uploaded as the `load-test-result` artifact.
- Job summary table with the fields listed in `data-model.md` §4, including the one-identity
  limitation (research R7).
- When a run is used as verification evidence, its figures are copied into
  `docs/operations/load-test-baseline.md` with the commit SHA and date.

## Cleanup

Seeded tenants are **kept**, not deleted, between runs: re-creating them every run adds writes to a
read test and churns the audit log. They are dev-only data and disappear with the environment on
`terraform destroy`.
