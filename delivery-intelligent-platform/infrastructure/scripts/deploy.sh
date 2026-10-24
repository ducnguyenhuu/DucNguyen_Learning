#!/usr/bin/env bash
# Manual first deploy (FR-012): build -> scan -> push -> terraform apply with the new image tag.
#
# The scan step is not optional and not skippable via a flag — Constitution Quality
# Gates require "No unresolved high or critical finding" on every container image
# change (analyze finding D1), and this is a new build each time, not a reuse of an
# already-scanned image. Reuses the existing S5 Trivy scripts rather than
# reimplementing scanning.
#
# The container app is a Terraform resource (ADR-023), but Terraform ignores its image tag
# (lifecycle ignore_changes), so the image is owned by whoever deploys it. The first deploy
# creates the app with `terraform apply`; every later deploy runs `az containerapp update`,
# the same command the CI/CD pipeline uses. Requires `terraform init` to have been run in
# infrastructure/terraform and a dev.tfvars there.
#
# Usage: ./deploy.sh <acr-login-server> <image-tag>
# Example: ./deploy.sh acrdipdev.azurecr.io v1

set -euo pipefail

if [ $# -ne 2 ]; then
    echo "usage: deploy.sh <acr-login-server> <image-tag>" >&2
    exit 2
fi

ACR_LOGIN_SERVER="$1"
IMAGE_TAG="$2"
IMAGE_NAME="identity-api"
LOCAL_TAG="${IMAGE_NAME}:${IMAGE_TAG}"
REMOTE_TAG="${ACR_LOGIN_SERVER}/${IMAGE_NAME}:${IMAGE_TAG}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
TERRAFORM_DIR="${SCRIPT_DIR}/../terraform"

echo "1/6 — Building ${LOCAL_TAG}..."
docker build -t "${LOCAL_TAG}" "${REPO_ROOT}"

echo "2/6 — Scanning for vulnerabilities (Constitution Quality Gates, analyze finding D1)..."
"${SCRIPT_DIR}/scan-image-vulnerabilities.sh" "${LOCAL_TAG}"

echo "3/6 — Scanning for secrets..."
"${SCRIPT_DIR}/scan-image-secrets.sh" "${LOCAL_TAG}"

echo "4/6 — Logging in to ACR and tagging..."
az acr login --name "$(echo "${ACR_LOGIN_SERVER}" | cut -d. -f1)"
docker tag "${LOCAL_TAG}" "${REMOTE_TAG}"

echo "5/6 — Pushing ${REMOTE_TAG}..."
docker push "${REMOTE_TAG}"

APP="$(terraform -chdir="${TERRAFORM_DIR}" output -raw container_app_name 2>/dev/null || true)"
RG="$(terraform -chdir="${TERRAFORM_DIR}" output -raw resource_group_name 2>/dev/null || true)"

# A new revision only takes traffic once its probes pass; if it never does, the previous
# revision keeps serving and this step fails (US4).
if [ -n "${APP}" ] && az containerapp show --name "${APP}" --resource-group "${RG}" >/dev/null 2>&1; then
    echo "6/6 — Updating ${APP} to ${REMOTE_TAG}..."
    az containerapp update --name "${APP}" --resource-group "${RG}" --image "${REMOTE_TAG}"
else
    echo "6/6 — First deploy: applying Terraform with api_image_tag=${IMAGE_TAG}..."
    terraform -chdir="${TERRAFORM_DIR}" apply -var-file=dev.tfvars -var "api_image_tag=${IMAGE_TAG}"
fi

echo "Deploy complete: ${REMOTE_TAG}"
