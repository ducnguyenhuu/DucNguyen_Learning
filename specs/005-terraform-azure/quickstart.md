# Quickstart: Terraform → Azure Infrastructure

**Branch**: `005-terraform-azure` | **Date**: 2026-09-26, revised 2026-10-16 for Container Apps (ADR-023)

## Prerequisites

1. **Azure subscription** with Owner or Contributor + User Access Administrator role
2. **Azure CLI** (`az`) installed and authenticated (`az login`)
3. **Terraform** ≥ 1.9 installed
4. **Docker** running (to build and push the container image)
5. **New Relic account** with an active ingest licence key

## Step 1 — Bootstrap Terraform State Backend

This is a one-time operation. It creates the Azure Storage Account that holds Terraform's remote state.

```bash
cd infrastructure/scripts
./bootstrap-state.sh
```

The script creates:
- Resource group `rg-dip-tfstate`
- Storage account (globally unique name)
- Blob container `tfstate`

Note the storage account name — it goes into the Terraform backend config.

## Step 2 — Configure Variables

```bash
cd infrastructure/terraform
cp dev.tfvars.example dev.tfvars
```

Edit `dev.tfvars` with your values:
- `subscription_id` — your Azure subscription
- `tenant_id` — your Entra ID tenant
- `sql_admin_object_id` — your user or group object ID for SQL admin
- `new_relic_licence_key` — your New Relic ingest key
- `acr_name` — a globally unique name (alphanumeric only)

## Step 3 — Provision Infrastructure

```bash
cd infrastructure/terraform

terraform init \
  -backend-config="resource_group_name=rg-dip-tfstate" \
  -backend-config="storage_account_name=<from-step-1>" \
  -backend-config="container_name=tfstate" \
  -backend-config="key=dev.tfstate"

terraform plan -var-file=dev.tfvars -target=module.acr -out=dev.tfplan
terraform apply dev.tfplan
```

This first, targeted apply creates only the registry (and its dependencies). The container app cannot exist before an image does, and a plan of the full config fails with a clear message until `api_image_tag` is set. Steps 4–5 do the rest.

## Step 4 — Build, Scan, Push and Deploy

`deploy.sh` builds the S5 image, runs the Trivy vulnerability and secret scans (a finding fails the script before anything is pushed), pushes to ACR, then — because the app does not exist yet — runs the full `terraform apply` with `api_image_tag` set. That apply provisions everything else: Container Apps environment and app, APIM, Front Door.

```bash
cd infrastructure/scripts
ACR=$(terraform -chdir=../terraform output -raw acr_login_server)
./deploy.sh "$ACR" v1
```

**Expected duration**: 30–50 minutes (APIM Developer tier takes ~30–45 min).

**Expected outputs**: Front Door endpoint URL, ACR login server, container app name, Key Vault URI.

## Step 5 — Confirm the Container App

```bash
APP=$(terraform -chdir=infrastructure/terraform output -raw container_app_name)
RG=$(terraform -chdir=infrastructure/terraform output -raw resource_group_name)

az containerapp replica list --name "$APP" --resource-group "$RG" -o table   # 2 replicas Running
az containerapp logs show --name "$APP" --resource-group "$RG" --container tenancy-api --tail 20
```

## Step 6 — Re-deploying

Every later deploy is the same command with a new tag. Once the app exists, `deploy.sh` runs `az containerapp update --image` instead of Terraform:

```bash
./deploy.sh "$ACR" v2
```

Terraform owns the app's shape but ignores its image tag (`ignore_changes`), so a later `terraform apply` never reverts a deploy. The image is owned by `deploy.sh` and, from S7, the CI/CD pipeline.

## Step 7 — End-to-End Verification

### 7a — Health through Front Door

```bash
FRONTDOOR_URL=$(terraform -chdir=infrastructure/terraform output -raw frontdoor_endpoint)
curl -s "$FRONTDOOR_URL/health/live"   # → 200 Healthy
curl -s "$FRONTDOOR_URL/health/ready"  # → 200 Healthy (SQL reachable via managed identity)
```

### 7b — Telemetry in New Relic

1. Trigger a few requests through Front Door
2. Open New Relic → Distributed Tracing
3. Search for service `Tenancy.Api`
4. Verify traces show the full span: Front Door → APIM → Container Apps → SQL

### 7c — No Secrets in Manifests

```bash
# Verify no inline secret values or passwords on the running app
az containerapp show --name "$APP" --resource-group "$RG" -o json \
  | grep -i "password\|\"value\".*licen" && echo "FAIL: secrets found" || echo "PASS: no secrets"
# The licence key must be a Key Vault reference, not an inline value
az containerapp show --name "$APP" --resource-group "$RG" --query "properties.configuration.secrets" -o json

# Verify no secrets in checked-in infrastructure files
grep -ri "password\|licence_key\|license_key" infrastructure/ --include='*.tf' --include='*.sh' --include='*.tftpl' | grep -v "var\.new_relic_licence_key\|variable\|new_relic_licence_key" && echo "FAIL" || echo "PASS"
```

## Step 8 — Broken Revision Recovery (US4)

FR-014 requires ≥2 replicas in single revision mode (see [contracts/container-app.md](contracts/container-app.md)) precisely so this scenario never drops traffic — verify that explicitly, not just that recovery eventually happens.

```bash
# Optional: start a background poll to prove zero dropped requests throughout
while true; do curl -s -o /dev/null -w "%{http_code} " "$FRONTDOOR_URL/health/live"; sleep 1; done &
POLL_PID=$!

# Deploy a known-bad image tag. The update is expected to fail or time out.
az containerapp update --name "$APP" --resource-group "$RG" \
  --image "$ACR/tenancy-api:nonexistent-tag" || true

# Observe: the new revision fails provisioning, the old revision stays active and serving
az containerapp revision list --name "$APP" --resource-group "$RG" -o table

# Recover by redeploying the known-good tag
cd infrastructure/scripts
./rollback.sh v1

# Stop the poll and confirm every response was 200 — no dropped requests
kill $POLL_PID
```

## Step 9 — Teardown

```bash
cd infrastructure/terraform
terraform destroy -var-file=dev.tfvars -auto-approve
```

**Expected duration**: 10–20 minutes.

Verify the subscription is empty:
```bash
az resource list --resource-group rg-dip-dev --output table
# Should return empty or "Resource group not found"
```

The state backend resource group (`rg-dip-tfstate`) is intentionally **not** destroyed — it holds the state file and is reused across apply/destroy cycles.

## Step 10 — Full Rebuild Verification (SC-002)

SC-002 defines "identical" as **configuration-identical** — same resource types, SKUs, settings, and topology — not literally identical resource IDs or IP addresses, which Azure reassigns on every fresh `apply`.

```bash
terraform apply -var-file=dev.tfvars -auto-approve

# Verify configuration-identical: a plan against the same .tfvars shows zero diffs
terraform plan -var-file=dev.tfvars -detailed-exitcode
# Exit code 0 = no changes (PASS). Exit code 2 = drift/diff detected (FAIL for SC-002).

# Re-run Steps 4–7 to verify the rebuilt environment behaves identically
```

## Requirement Coverage

| Requirement | Verified By |
|-------------|-------------|
| FR-001 (Terraform, no portal) | Steps 2–3 |
| FR-002 (Remote state) | Step 1 |
| FR-003 (Dev environment) | Step 3 (dev.tfvars) |
| FR-004 (Managed identity for SQL) | Step 7a (ready check proves SQL connection) |
| FR-005 (Managed identity for KV) | Step 7b (traces prove licence key loaded) |
| FR-006 (Private endpoints) | Step 3 (Terraform provisions them) |
| FR-007 (Front Door → APIM → Container Apps) | Step 7a |
| FR-008 (OTel Collector → New Relic) | Step 7b |
| FR-009 (Container app with probes) | Steps 4–5 |
| FR-010 (terraform destroy) | Step 9 |
| FR-011 (Drift detection) | `terraform plan` after any manual change |
| FR-012 (Manual first deploy) | Steps 4–7 |
| FR-013 (Recovery by redeploying a good tag) | Step 8 |
| FR-014 (≥2 replicas, single revision, zero-downtime rollout) | Step 8 (background poll shows no dropped requests) |
| SC-001 (< 90 min) | Steps 1–7 total |
| SC-002 (Rebuild configuration-identical) | Step 10 (`terraform plan -detailed-exitcode` = 0) |
| SC-004 (Zero secrets in code) | Step 7c |
| SC-005 (Telemetry < 60s) | Step 7b |
| SC-006 (Recovery < 5 min) | Step 8 |
