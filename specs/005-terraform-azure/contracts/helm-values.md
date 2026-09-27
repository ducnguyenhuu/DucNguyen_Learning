# Helm Values Contract

**Branch**: `005-terraform-azure` | **Date**: 2026-09-26

## values.yaml (defaults)

```yaml
# -- Tenancy API
api:
  image:
    repository: ""          # Required: ACR login server + image name
    tag: "latest"
  replicas: 2               # FR-014: ≥2 required for zero-downtime rollback (US4)
  rollout:
    maxUnavailable: 0       # FR-014: old replicas keep serving until new ones are Ready
    maxSurge: 1
  resources:
    requests:
      cpu: "100m"
      memory: "128Mi"
    limits:
      cpu: "500m"
      memory: "256Mi"
  serviceAccount:
    name: "tenancy-api"
    annotations: {}         # Overridden in values-dev.yaml with workload identity client ID
  probes:
    liveness:
      path: /health/live
      port: 8080
      initialDelaySeconds: 5
      periodSeconds: 10
    readiness:
      path: /health/ready
      port: 8080
      initialDelaySeconds: 10
      periodSeconds: 5
  env: []                   # Additional environment variables

# -- OTel Collector
otelCollector:
  enabled: true
  image:
    repository: "otel/opentelemetry-collector-contrib"
    tag: "0.111.0"          # Pin to known-good version
  replicas: 1
  resources:
    requests:
      cpu: "50m"
      memory: "128Mi"
    limits:
      cpu: "250m"
      memory: "256Mi"
  serviceAccount:
    name: "otel-collector"
    annotations: {}
  ports:
    grpc: 4317
    http: 4318

# -- Key Vault CSI
keyVault:
  enabled: true
  vaultName: ""             # Required: Key Vault name
  tenantId: ""              # Required: Azure AD tenant ID
  secrets:
    - name: new-relic-licence-key
      alias: NEW_RELIC_LICENCE_KEY

# -- Ingress
ingress:
  enabled: true
  className: "nginx"
  annotations: {}
  host: ""                  # Optional: if empty, matches all hosts
```

## values-dev.yaml (dev overrides)

```yaml
api:
  image:
    repository: "acrdipdev.azurecr.io/tenancy-api"
  serviceAccount:
    annotations:
      azure.workload.identity/client-id: "<tenancy-api-managed-identity-client-id>"
  env:
    - name: ASPNETCORE_URLS
      value: "http://+:8080"
    - name: Https__RedirectionEnabled
      value: "false"
    - name: ConnectionStrings__DefaultConnection
      value: "Server=sql-dip-dev.database.windows.net;Database=sqldb-dip-dev;Authentication=Active Directory Default;"
    - name: OTEL_EXPORTER_OTLP_ENDPOINT
      value: "http://otel-collector:4317"

otelCollector:
  serviceAccount:
    annotations:
      azure.workload.identity/client-id: "<otel-collector-managed-identity-client-id>"

keyVault:
  vaultName: "kv-dip-dev"
  tenantId: "<azure-ad-tenant-id>"
```

## Notes

- The `azure.workload.identity/client-id` annotation values are outputs from Terraform's identity module and must be substituted during deploy.
- `ConnectionStrings__DefaultConnection` uses `Authentication=Active Directory Default` which works with `DefaultAzureCredential` — the managed identity token is acquired automatically, no password in the connection string.
- The OTel Collector config is mounted as a ConfigMap; the New Relic licence key is mounted as a CSI volume from Key Vault.
- `api.replicas: 2` and `rollout.maxUnavailable: 0` are deliberate, not arbitrary defaults — clarified 2026-09-26 (spec.md Clarifications) so US4's broken-rollout scenario is actually testable: with 1 replica, Kubernetes' default strategy tears down the old pod before the new one is Ready, which would cause a real outage regardless of the new image's health. `otelCollector.replicas` stays at 1 — it is not on the user-facing request path and its own restart does not drop application traffic.
