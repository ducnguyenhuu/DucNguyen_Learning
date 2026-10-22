#!/usr/bin/env bash
#
# Writes infrastructure/github/pipeline.auto.tfvars.json from what is already deployed, so the
# nine repository variables the pipeline reads never have to be copied by hand. The file holds
# identifiers and hostnames only; *.tfvars* is git-ignored regardless.
#
# Needs: az login, and both `persistent/` and the S6 root applied (terraform init'd locally).
# Usage: pipeline-variables.sh [api-app-display-name]
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
API_APP_NAME="${1:-Delivery Intelligence API}"
TF="${REPO_ROOT}/infrastructure/terraform"

out() { terraform -chdir="$1" output -raw "$2"; }

API_APP_ID=$(az ad app list --display-name "${API_APP_NAME}" --query '[0].appId' -o tsv)
[ -n "${API_APP_ID}" ] || { echo "no app registration named '${API_APP_NAME}'" >&2; exit 1; }

jq -n \
    --arg tenant "$(az account show --query tenantId -o tsv)" \
    --arg sub "$(az account show --query id -o tsv)" \
    --arg deployer "$(out "${TF}/persistent" deployer_client_id)" \
    --arg loadtest "$(out "${TF}/persistent" loadtest_client_id)" \
    --arg audience "api://${API_APP_ID}" \
    --arg acr "$(out "${TF}" acr_login_server)" \
    --arg rg "$(out "${TF}" resource_group_name)" \
    --arg app "$(out "${TF}" container_app_name)" \
    --arg fd "$(out "${TF}" frontdoor_endpoint | sed 's#^https://##')" \
    '{pipeline_variables: {
        AZURE_TENANT_ID: $tenant, AZURE_SUBSCRIPTION_ID: $sub,
        AZURE_DEPLOYER_CLIENT_ID: $deployer, AZURE_LOADTEST_CLIENT_ID: $loadtest,
        TENANCY_API_APP_ID_URI: $audience, ACR_LOGIN_SERVER: $acr,
        RESOURCE_GROUP: $rg, CONTAINER_APP_NAME: $app, FRONTDOOR_ENDPOINT: $fd}}' \
    >"${REPO_ROOT}/infrastructure/github/pipeline.auto.tfvars.json"

echo "wrote infrastructure/github/pipeline.auto.tfvars.json"
