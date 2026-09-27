#!/usr/bin/env bash
# Wraps `helm rollback` + a rollout-status wait, per quickstart.md Step 8/FR-013.
#
# Usage: ./rollback.sh [revision]
# If no revision is given, rolls back to the immediately previous revision.

set -euo pipefail

RELEASE="tenancy"
REVISION="${1:-}"

if [ -z "${REVISION}" ]; then
    echo "Rolling back ${RELEASE} to the previous revision..."
    helm rollback "${RELEASE}"
else
    echo "Rolling back ${RELEASE} to revision ${REVISION}..."
    helm rollback "${RELEASE}" "${REVISION}"
fi

echo "Waiting for rollout to complete..."
kubectl rollout status deployment/tenancy-api --timeout=2m

echo "Rollback complete. Current revision:"
helm history "${RELEASE}" --max 1
