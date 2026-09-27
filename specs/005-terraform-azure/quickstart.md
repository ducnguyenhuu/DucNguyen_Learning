# Quickstart: Terraform → Azure Infrastructure

**Branch**: `005-terraform-azure` | **Date**: 2026-09-26

## Prerequisites

1. **Azure subscription** with Owner or Contributor + User Access Administrator role
2. **Azure CLI** (`az`) installed and authenticated (`az login`)
3. **Terraform** ≥ 1.9 installed
4. **Helm** 3 installed
5. **kubectl** installed
6. **Docker** running (to build and push the container image)
7. **New Relic account** with an active ingest licence key

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

terraform plan -var-file=dev.tfvars -out=dev.tfplan
terraform apply dev.tfplan
```

**Expected duration**: 30–50 minutes (APIM Developer tier takes ~30–45 min).

**Expected outputs**: Front Door endpoint URL, ACR login server, AKS cluster name, Key Vault URI.

## Step 4 — Connect to AKS

```bash
az aks get-credentials \
  --resource-group rg-dip-dev \
  --name aks-dip-dev

kubectl get nodes   # Should show 1-2 nodes in Ready state
```

## Step 5 — Build and Push Container Image

```bash
az acr login --name acrdipdev

docker build -t acrdipdev.azurecr.io/tenancy-api:v1 .
docker push acrdipdev.azurecr.io/tenancy-api:v1
```

## Step 6 — Deploy with Helm

```bash
cd infrastructure/helm

helm upgrade --install tenancy ./tenancy \
  -f tenancy/values-dev.yaml \
  --set api.image.tag=v1 \
  --namespace default \
  --wait --timeout 5m
```

Verify pods are running:
```bash
kubectl get pods
kubectl logs deployment/tenancy-api --tail=20
```

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
4. Verify traces show the full span: Front Door → APIM → AKS → SQL

### 7c — No Secrets in Manifests

```bash
# Verify no secrets in Kubernetes objects
kubectl get secrets -o yaml | grep -i "password\|connection.*string\|licence\|license" && echo "FAIL: secrets found" || echo "PASS: no secrets"

# Verify no secrets in Helm values committed to git
grep -ri "password\|licence_key\|license_key" infrastructure/helm/ && echo "FAIL" || echo "PASS"
```

## Step 8 — Broken Rollout Recovery (US4)

FR-014 requires ≥2 replicas with `maxUnavailable: 0` (see [contracts/helm-values.md](contracts/helm-values.md)) precisely so this scenario never drops traffic — verify that explicitly, not just that recovery eventually happens.

```bash
# Optional: start a background poll to prove zero dropped requests throughout
while true; do curl -s -o /dev/null -w "%{http_code} " "$FRONTDOOR_URL/health/live"; sleep 1; done &
POLL_PID=$!

# Deploy a known-bad image
helm upgrade tenancy ./tenancy \
  -f tenancy/values-dev.yaml \
  --set api.image.tag=nonexistent-tag \
  --namespace default \
  --timeout 2m || true

# Observe: new pods in ImagePullBackOff, but old replicas keep Ready and serving
# (maxUnavailable: 0 means the old ReplicaSet is never scaled down until the new one is healthy)
kubectl get pods
kubectl rollout status deployment/tenancy-api  # Should show stalled

# Rollback
helm rollback tenancy 1
kubectl rollout status deployment/tenancy-api  # Should show success

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

# Re-run Steps 5–7 to verify the rebuilt environment behaves identically
```

## Requirement Coverage

| Requirement | Verified By |
|-------------|-------------|
| FR-001 (Terraform, no portal) | Steps 2–3 |
| FR-002 (Remote state) | Step 1 |
| FR-003 (Dev environment) | Step 3 (dev.tfvars) |
| FR-004 (Managed identity for SQL) | Step 7a (ready check proves SQL connection) |
| FR-005 (Workload identity for KV) | Step 7b (traces prove licence key loaded) |
| FR-006 (Private endpoints) | Step 3 (Terraform provisions them) |
| FR-007 (Front Door → APIM → AKS) | Step 7a |
| FR-008 (OTel Collector → New Relic) | Step 7b |
| FR-009 (Helm chart with probes) | Step 6 |
| FR-010 (terraform destroy) | Step 9 |
| FR-011 (Drift detection) | `terraform plan` after any manual change |
| FR-012 (Manual first deploy) | Steps 5–7 |
| FR-013 (Rollback) | Step 8 |
| FR-014 (≥2 replicas, zero-downtime rollout) | Step 8 (background poll shows no dropped requests) |
| SC-001 (< 90 min) | Steps 1–7 total |
| SC-002 (Rebuild configuration-identical) | Step 10 (`terraform plan -detailed-exitcode` = 0) |
| SC-004 (Zero secrets in code) | Step 7c |
| SC-005 (Telemetry < 60s) | Step 7b |
| SC-006 (Recovery < 5 min) | Step 8 |
