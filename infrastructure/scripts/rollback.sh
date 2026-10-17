#!/usr/bin/env bash
# Recovers from a bad rollout by redeploying a previously good image tag (quickstart.md
# Step 8 / FR-013). In single revision mode a revision that fails its probes never takes
# traffic and the previous revision keeps serving (ADR-023), so recovery is replacing the
# failed revision with a known-good one, not shifting traffic.
#
# Usage: ./rollback.sh <known-good-image-tag>

set -euo pipefail

if [ $# -ne 1 ]; then
    echo "usage: rollback.sh <known-good-image-tag>" >&2
    exit 2
fi

GOOD_TAG="$1"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERRAFORM_DIR="${SCRIPT_DIR}/../terraform"

echo "Redeploying known-good tag ${GOOD_TAG}..."
terraform -chdir="${TERRAFORM_DIR}" apply -var-file=dev.tfvars -var "api_image_tag=${GOOD_TAG}"

APP="$(terraform -chdir="${TERRAFORM_DIR}" output -raw container_app_name)"
RG="$(terraform -chdir="${TERRAFORM_DIR}" output -raw resource_group_name)"
echo "Revisions now:"
az containerapp revision list --name "${APP}" --resource-group "${RG}" \
    --query "[].{name:name,active:properties.active,health:properties.healthState,traffic:properties.trafficWeight}" -o table
