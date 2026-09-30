# GitHub Repository Configuration Contract

**Branch**: `006-ci-cd` | **Date**: 2026-09-29
**Managed by**: `infrastructure/github/` (Terraform, `integrations/github` provider), applied by a
human with `GITHUB_TOKEN=$(gh auth token)`. Never applied by the pipeline itself.

## Ruleset: `main`

| Rule | Setting |
|---|---|
| Target | `refs/heads/main` |
| Enforcement | active |
| Bypass actors | **none** — admins included |
| Pull request required | yes, 0 required approvals (solo project — see research R6) |
| Required status checks | `commit-messages`, `secret-scan`, `build-test`, `integration-test`, `container-scan` |
| Require branches up to date | yes |
| Block force pushes | yes |
| Block deletion | yes |

Feature branches (`NNN-*`) carry no rules, so the speckit branch-per-feature workflow is unaffected.

## Environments

| Environment | Deployment branches | Required reviewers | Admin bypass | Purpose |
|---|---|---|---|---|
| `dev` | `main` only | none | — | Federated-credential subject for both identities |
| `production` | `main` only | project owner | **disabled** (`can_admins_bypass = false`) | The approval gate (FR-009); no-op stage in this slice |

## Repository variables

Listed in `contracts/pipeline.md` → *Inputs*. Values come from `terraform output` of the
`persistent/` and S6 roots.

## Repository secrets

**None.** This list is intentionally empty and is part of the contract: a pull request that adds a
repository or environment secret contradicts Constitution Principle V and must instead be solved
with OIDC federation or a non-sensitive variable.

## State

Own state key, `github.tfstate`, in the S6 bootstrap storage account. This root is **not** destroyed
between sessions — it is free and persistent.
