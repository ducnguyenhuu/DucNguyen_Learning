# One container app, two containers (ADR-023): the Identity API and the OTel Collector as a
# sidecar. Containers in a replica share a network namespace, so the API exports OTLP to
# localhost. Single revision mode: a new revision only takes traffic once its probes pass,
# and the previous revision keeps serving until then — this is what makes a broken rollout
# invisible to callers (FR-014, US4).
resource "azurerm_container_app" "api" {
  name                         = "ca-identity-api-${var.environment}"
  resource_group_name          = var.resource_group_name
  container_app_environment_id = azurerm_container_app_environment.main.id
  revision_mode                = "Single"
  tags                         = var.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [var.identity_api_identity_id, var.otel_collector_identity_id]
  }

  registry {
    server   = var.acr_login_server
    identity = var.identity_api_identity_id
  }

  # Resolved by the platform from Key Vault with the collector's identity; mounted below as
  # a file, so the licence key is never an environment variable or a Terraform value.
  secret {
    name                = "new-relic-licence-key"
    key_vault_secret_id = var.new_relic_secret_id
    identity            = var.otel_collector_identity_id
  }

  ingress {
    external_enabled           = true
    target_port                = 8080
    transport                  = "http"
    allow_insecure_connections = false

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    min_replicas = var.api_min_replicas
    max_replicas = var.api_max_replicas

    volume {
      name         = "kv-secrets"
      storage_type = "Secret"
    }

    container {
      name   = "identity-api"
      image  = "${var.acr_login_server}/identity-api:${var.api_image_tag}"
      cpu    = 0.5
      memory = "1Gi"

      env {
        name  = "ASPNETCORE_URLS"
        value = "http://+:8080"
      }
      env {
        name  = "ASPNETCORE_ENVIRONMENT"
        value = "Production"
      }
      env {
        name  = "Https__RedirectionEnabled"
        value = "false"
      }
      # Managed identity, no password (Principle V). AZURE_CLIENT_ID selects the
      # user-assigned identity for the SQL token.
      env {
        name  = "ConnectionStrings__DefaultConnection"
        value = "Server=${var.sql_server_fqdn};Database=${var.sql_database_name};Authentication=Active Directory Default;"
      }
      env {
        name  = "AZURE_CLIENT_ID"
        value = var.identity_api_client_id
      }
      env {
        name  = "OTEL_EXPORTER_OTLP_ENDPOINT"
        value = "http://localhost:4317"
      }

      startup_probe {
        transport               = "HTTP"
        port                    = 8080
        path                    = "/health/live"
        interval_seconds        = 5
        failure_count_threshold = 12
      }

      liveness_probe {
        transport               = "HTTP"
        port                    = 8080
        path                    = "/health/live"
        interval_seconds        = 10
        failure_count_threshold = 3
      }

      readiness_probe {
        transport               = "HTTP"
        port                    = 8080
        path                    = "/health/ready"
        interval_seconds        = 5
        failure_count_threshold = 3
      }
    }

    container {
      name   = "otel-collector"
      image  = "otel/opentelemetry-collector-contrib:0.111.0"
      cpu    = 0.25
      memory = "0.5Gi"
      args   = ["--config=env:OTEL_COLLECTOR_CONFIG"]

      env {
        name  = "OTEL_COLLECTOR_CONFIG"
        value = templatefile("${path.module}/otel-collector-config.yaml.tftpl", { sample_rate = var.otel_sample_rate })
      }

      volume_mounts {
        name = "kv-secrets"
        path = "/mnt/secrets"
      }
    }
  }

  lifecycle {
    # Terraform owns the app's shape; the CI/CD pipeline and deploy.sh own which image tag
    # runs (`az containerapp update --image`). Without this, the next apply would revert
    # the pipeline's deploy to whatever api_image_tag was last passed.
    ignore_changes = [template[0].container[0].image]

    precondition {
      condition     = var.api_image_tag != ""
      error_message = "api_image_tag is empty. Build and push the image first (infrastructure/scripts/deploy.sh); the container app cannot be created without a real image."
    }
  }

  depends_on = [azurerm_role_assignment.acr_pull]
}
