# Quickstart: CI/CD Pipeline with Performance Verification

**Branch**: `006-ci-cd` | **Date**: 2026-09-29

Steps 1–3 are one-time setup. Steps 4–8 verify each user story. Anything touching Azure needs the
S6 environment applied first (`specs/005-terraform-azure/quickstart.md`).

## Prerequisites

- S6 applied: `terraform -chdir=infrastructure/terraform output` shows ACR, AKS, and Front Door
- `az login`, `gh auth login`, Terraform ≥ 1.9
- ADR-022 accepted (done 2026-09-29)

## Step 1 — Persistent identities (survive S6 destroy cycles)

```bash
cd infrastructure/terraform/persistent
terraform init \
  -backend-config="resource_group_name=rg-dip-tfstate" \
  -backend-config="storage_account_name=<from bootstrap-state.sh>" \
  -backend-config="container_name=tfstate" \
  -backend-config="key=persistent.tfstate"
terraform apply
```

Creates `id-github-deployer`, `id-loadtest-client`, their GitHub federated credentials, and (after
ADR-022) the `Tenancy.Automation.Member` app role and its assignment.

## Step 2 — Re-apply S6 with the amendments

```bash
cd infrastructure/terraform
terraform apply -var-file=dev.tfvars
```

Adds AKS Entra RBAC, the all-method APIM operations, and the deployer's role assignments against
the ACR and AKS that currently exist.

## Step 3 — Repository configuration

```bash
cd infrastructure/github
export GITHUB_TOKEN=$(gh auth token)
terraform init -backend-config=... -backend-config="key=github.tfstate"
terraform apply
```

Verify:

```bash
gh api repos/{owner}/{repo}/rulesets --jq '.[].name'          # → main
gh api repos/{owner}/{repo}/environments --jq '.environments[].name'   # → dev, production
gh secret list                                                # → empty (by contract)
```

## Step 4 — US1: commit to dev, unattended

Merge a trivial conforming change (e.g. `docs(ci-cd): note pipeline duration`) through a PR.

- Every job in `contracts/pipeline.md` runs without a click until `production` pauses.
- `curl -s "https://$FRONTDOOR_ENDPOINT/health/ready"` → 200, and the deployed image tag equals the commit SHA:
  `kubectl get deploy tenancy-api -o jsonpath='{.spec.template.spec.containers[0].image}'`
- Record run duration. Repeat until 10 consecutive runs are timed (SC-001: 95% under 20 min).

## Step 5 — US2: each gate rejects a planted violation

Run the self-test, then observe each failure in a real PR on a throwaway branch:

```bash
gh workflow run gate-selftest.yml && gh run watch
```

| Planted in a PR | Failing job | Message names |
|---|---|---|
| `Tenancy.Domain` file using a `Tenancy.Infrastructure` type | `build-test` | the architecture rule and file |
| A synthetic access key in any file | `secret-scan` | file and line |
| A package version with a known high advisory | `build-test` (restore) | package, version, advisory |
| A commit titled `fixed stuff` | `commit-messages` | the SHA and expected format |

In each case: the PR cannot merge (ruleset), no image reaches ACR, dev is untouched.

## Step 6 — US3: production requires a human

1. On a run paused at `production`, **approve** → the job summary shows approver, SHA, timestamp.
2. On another, **reject** → the job fails; nothing proceeds.
3. Attempt a bypass: as the repository admin, try to deploy to `production` without review (e.g.
   re-run the job, or push a workflow change that removes `environment:`). The environment's
   protection still applies, and the ruleset blocks unreviewed changes to `main`.
4. Approval expiry: approve a run whose commit is > 7 days old → the job fails with *Approval expired*.

## Step 7 — FR-014: preempt-latest

Merge two changes to `main` within a minute. The older run shows **cancelled** with
`Superseded by <newer sha>` in its summary; the deployed image is the newer SHA; no deploy was
interrupted mid-upgrade (`helm history tenancy` shows no failed revision from the cancellation).

## Step 8 — US4: spec 001 SC-003

After a green `load-test` job, open its summary:

- p95 for `phase:steady, kind:tenant-read` < 1000 ms
- error rate < 1%
- 50 VUs, 20 tenants, one identity (limitation stated)

Copy the figures, commit SHA, and date into `docs/operations/load-test-baseline.md`, and mark spec
001 SC-003 **verified** in its Deferred Requirements table.

## Step 9 — Torn-down environment (edge case)

After `terraform destroy` of S6, push to `main`: `deploy-dev` fails at preflight with the
*Dev environment not found* message, in seconds, and `load-test` does not start.

## Requirement Coverage

| Requirement | Verified by |
|---|---|
| FR-001 stage sequence | Step 4 |
| FR-002 < 20 min | Step 4 (timed runs) |
| FR-003 unattended | Step 4 |
| FR-004 architecture gate | Step 5 + `gate-selftest.yml` |
| FR-005 secret gate | Step 5 + `gate-selftest.yml` |
| FR-006 dependency gate | Step 5 + `gate-selftest.yml` |
| FR-007 commit gate | Step 5 + `gate-selftest.yml` |
| FR-008 image gate | `container-scan` (S5 bait proof, every run) |
| FR-009 approval required | Step 6.1–6.3 |
| FR-010 approval recorded | Step 6.1 |
| FR-011 branch protection | Step 3 verify + Step 5 (unmergeable PRs) |
| FR-012 load scenario | Step 8 |
| FR-013 thresholds | Step 8 (+ a deliberately slowed build fails the job) |
| FR-014 preempt-latest | Step 7 |
| FR-015 no partial deploy | Step 7 (`helm history`) + `--atomic` |
| FR-016 config as code | Steps 1–3 — everything is `terraform apply` |
| SC-001 | Step 4 (10 runs) |
| SC-002 | Step 5 |
| SC-003 | Step 6 |
| SC-004 | Step 8 |
| SC-005 | Any failure in Step 5 — identified from the run page alone |
| SC-006 | Steps 1–3 on a fresh clone |
