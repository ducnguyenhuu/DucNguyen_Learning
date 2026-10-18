# Repository configuration as code (specs/006-ci-cd/contracts/github-config.md). Applied by a
# human with GITHUB_TOKEN=$(gh auth token) — never by the pipeline it configures.

provider "github" {
  owner = var.github_owner
}

data "github_repository" "this" {
  name = var.repository
}

data "github_user" "production_reviewer" {
  username = var.production_reviewer
}

# --- Environments ---------------------------------------------------------------------------

resource "github_repository_environment" "dev" {
  repository  = data.github_repository.this.name
  environment = "dev"

  deployment_branch_policy {
    protected_branches     = false
    custom_branch_policies = true
  }
}

resource "github_repository_environment_deployment_policy" "dev_main" {
  repository     = data.github_repository.this.name
  environment    = github_repository_environment.dev.environment
  branch_pattern = "main"
}

resource "github_repository_environment" "production" {
  repository          = data.github_repository.this.name
  environment         = "production"
  can_admins_bypass   = false
  prevent_self_review = false # solo project: the only reviewer is also the author (research R6)

  reviewers {
    users = [data.github_user.production_reviewer.id]
  }

  deployment_branch_policy {
    protected_branches     = false
    custom_branch_policies = true
  }
}

resource "github_repository_environment_deployment_policy" "production_main" {
  repository     = data.github_repository.this.name
  environment    = github_repository_environment.production.environment
  branch_pattern = "main"
}

# --- Repository variables (no secrets: see the contract) ------------------------------------

resource "github_actions_variable" "pipeline" {
  for_each = var.pipeline_variables

  repository    = data.github_repository.this.name
  variable_name = each.key
  value         = each.value
}

# --- Branch protection ----------------------------------------------------------------------

resource "github_repository_ruleset" "main" {
  name        = "main"
  repository  = data.github_repository.this.name
  target      = "branch"
  enforcement = "active"

  conditions {
    ref_name {
      include = ["refs/heads/main"]
      exclude = []
    }
  }

  # No bypass_actors block: admins are bound by the same rules (FR-011).

  rules {
    deletion         = true
    non_fast_forward = true

    pull_request {
      required_approving_review_count = 0
    }

    required_status_checks {
      strict_required_status_checks_policy = true

      dynamic "required_check" {
        for_each = var.required_checks
        content {
          context = required_check.value
        }
      }
    }
  }
}
