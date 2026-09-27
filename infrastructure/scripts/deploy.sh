#!/usr/bin/env bash
# Manual first deploy (FR-012): build -> scan -> push -> helm upgrade --install.
#
# The scan step is not optional and not skippable via a flag — Constitution Quality
# Gates require "No unresolved high or critical finding" on every container image
# change (analyze finding D1), and this is a new build each time, not a reuse of an
# already-scanned image. Reuses the existing S5 Trivy scripts rather than
# reimplementing scanning.
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
IMAGE_NAME="tenancy-api"
LOCAL_TAG="${IMAGE_NAME}:${IMAGE_TAG}"
REMOTE_TAG="${ACR_LOGIN_SERVER}/${IMAGE_NAME}:${IMAGE_TAG}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
HELM_CHART_DIR="${SCRIPT_DIR}/../helm/tenancy"

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

echo "6/6 — Deploying via Helm..."
helm upgrade --install tenancy "${HELM_CHART_DIR}" \
    -f "${HELM_CHART_DIR}/values-dev.yaml" \
    --set "api.image.repository=${ACR_LOGIN_SERVER}/${IMAGE_NAME}" \
    --set "api.image.tag=${IMAGE_TAG}" \
    --namespace default \
    --wait --timeout 5m

echo "Deploy complete: ${REMOTE_TAG}"
