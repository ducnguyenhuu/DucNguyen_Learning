#!/usr/bin/env bash
# One-time: provisions the Azure Storage Account that holds Terraform's remote state
# for the main infrastructure/terraform config. Idempotent — safe to re-run.
#
# Usage: ./bootstrap-state.sh [storage-account-name]
# If no name is given, one is generated deterministically from the subscription ID.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BOOTSTRAP_DIR="${SCRIPT_DIR}/../terraform/bootstrap"

SUBSCRIPTION_ID="$(az account show --query id -o tsv)"
DEFAULT_NAME="stdiptfstate$(echo "${SUBSCRIPTION_ID}" | tr -d '-' | cut -c1-8)"
STORAGE_ACCOUNT_NAME="${1:-${DEFAULT_NAME}}"

echo "Bootstrapping Terraform state backend..."
echo "  Subscription: ${SUBSCRIPTION_ID}"
echo "  Storage account: ${STORAGE_ACCOUNT_NAME}"

pushd "${BOOTSTRAP_DIR}" > /dev/null

terraform init
terraform apply \
  -var="storage_account_name=${STORAGE_ACCOUNT_NAME}" \
  -auto-approve

RESOURCE_GROUP="$(terraform output -raw resource_group_name)"
CONTAINER="$(terraform output -raw container_name)"

popd > /dev/null

echo ""
echo "State backend ready. Use these values for 'terraform init -backend-config':"
echo "  resource_group_name=${RESOURCE_GROUP}"
echo "  storage_account_name=${STORAGE_ACCOUNT_NAME}"
echo "  container_name=${CONTAINER}"
