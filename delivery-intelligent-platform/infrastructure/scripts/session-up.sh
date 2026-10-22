#!/usr/bin/env bash
#
# Starts a working session: builds the S6 dev environment and deploys the API into it.
# Run session-down.sh when you finish — the environment bills by the hour while it exists
# (roughly $0.20/hr, about $5-6 a day if forgotten).
#
# Does, in order: terraform init, registry apply (the app cannot exist before an image), then
# deploy.sh (build, scan, push, create the app and everything else), then refreshes the GitHub
# repository variables if infrastructure/github has been initialised.
#
# Needs: az login, Docker running, infrastructure/terraform/dev.tfvars, the state backend
# (bootstrap-state.sh) and infrastructure/terraform/persistent applied, and
# TF_VAR_new_relic_licence_key exported.
#
# Usage: session-up.sh [image-tag]     (default tag: the short git SHA)
set -euo pipefail

# shellcheck source=_session-lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_session-lib.sh"

TAG="${1:-$(git -C "${SCRIPT_DIR}" rev-parse --short HEAD)}"

require_azure_login
require_tfvars
docker info >/dev/null 2>&1 || { echo "Docker is not running." >&2; exit 2; }
[ -n "${TF_VAR_new_relic_licence_key:-}" ] \
    || { echo "Export TF_VAR_new_relic_licence_key first (never write it in a file)." >&2; exit 2; }

echo "== 1/4 terraform init"
terraform_init

echo "== 2/4 registry (the app needs an image before it can be created)"
terraform -chdir="${TERRAFORM_DIR}" apply -var-file=dev.tfvars -target=module.acr

echo "== 3/4 build, scan, push and deploy ${TAG}"
ACR="$(terraform -chdir="${TERRAFORM_DIR}" output -raw acr_login_server)"
"${SCRIPT_DIR}/deploy.sh" "${ACR}" "${TAG}"

echo "== 4/4 GitHub repository variables"
if [ -d "${SCRIPT_DIR}/../github/.terraform" ]; then
    "${SCRIPT_DIR}/pipeline-variables.sh"
    GITHUB_TOKEN="${GITHUB_TOKEN:-$(gh auth token)}" \
        terraform -chdir="${SCRIPT_DIR}/../github" apply -input=false -auto-approve
else
    echo "infrastructure/github is not initialised yet; skipping (see specs/006-ci-cd/quickstart.md Step 3)."
fi

echo
echo "Environment is up: $(terraform -chdir="${TERRAFORM_DIR}" output -raw frontdoor_endpoint)"
echo "It is costing money now. When you are done: infrastructure/scripts/session-down.sh"
