# Container App Contract

**Branch**: `005-terraform-azure` | **Date**: 2026-10-16 | Replaces the Helm values contract (ADR-023)

The Tenancy API and its OTel Collector sidecar are one `azurerm_container_app`
(`infrastructure/terraform/modules/containerapp/`). There is no chart or manifest.

## Inputs to the `containerapp` module

| Input | Default | Meaning |
|-------|---------|---------|
| `api_image_tag` | `""` | Tag already pushed to ACR. Empty fails the plan (precondition). `deploy.sh` sets it. |
| `api_min_replicas` | `2` | FR-014: at least 2, so a serving revision always exists during a rollout |
| `api_max_replicas` | `3` | Upper bound |
| `allowed_ingress_cidrs` | — | APIM public IPs as `/32`s; the only sources the ingress accepts (FR-007) |
| `otel_sample_rate` | `10` | Collector tail-sampling default-rate percentage |

## Resulting app

| Property | Value |
|----------|-------|
| Revision mode | `Single`: a new revision takes traffic only after its probes pass |
| Ingress | external, target port 8080, HTTPS only, IP allow-list |
| Identities | `id-tenancy-api` (ACR pull, SQL), `id-otel-collector` (Key Vault read) |
| API container | 0.5 vCPU / 1 GiB; startup + liveness on `/health/live`, readiness on `/health/ready` |
| Collector sidecar | `otel/opentelemetry-collector-contrib:0.111.0`, 0.25 vCPU / 0.5 GiB, config from env `OTEL_COLLECTOR_CONFIG` |
| Licence key | Key Vault secret reference, mounted as a file at `/mnt/secrets/new-relic-licence-key` |

## API container environment

| Variable | Value |
|----------|-------|
| `ASPNETCORE_URLS` | `http://+:8080` |
| `Https__RedirectionEnabled` | `false` (TLS terminates at Front Door) |
| `ConnectionStrings__DefaultConnection` | `Server=<sql fqdn>;Database=<db>;Authentication=Active Directory Default;` — no password |
| `AZURE_CLIENT_ID` | `id-tenancy-api` client ID, so `DefaultAzureCredential` picks the user-assigned identity |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://localhost:4317` — the sidecar shares the replica's network namespace |

## Notes

- Single revision mode plus `api_min_replicas = 2` is the FR-014 guarantee. Replicas of a bad revision never become ready, so the platform never swaps traffic to them.
- Recovery is `rollback.sh <known-good-tag>`: Terraform replaces the failed revision with a good one. There is no traffic-weight shifting in single revision mode.
- The Collector's own restart does not drop API traffic, but both containers restart together on every new revision.
