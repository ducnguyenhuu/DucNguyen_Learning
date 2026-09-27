#!/usr/bin/env bash
#
# FR-009: fails if the release-candidate image contains any secret finding, AND fails if the
# deliberately baited image (Dockerfile.secretbait) produces NO finding — a negative proof
# that the scan is actually capable of catching something, not merely one that happens not to
# fire (research.md R6). Both `--scanners secret` (filesystem) and `--image-config-scanners
# secret` (image config/history — where a secret passed as a build ENV hides) are run.
#
# Usage: scan-image-secrets.sh <release-candidate-image-tag>
set -euo pipefail

if [ $# -ne 1 ]; then
    echo "usage: scan-image-secrets.sh <release-candidate-image-tag>" >&2
    exit 2
fi

RC_IMAGE="$1"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BAIT_IMAGE="tenancy-api:bait"
BAIT_KEY="${REPO_ROOT}/secretbait.pem"

if ! command -v trivy >/dev/null 2>&1; then
    echo "trivy is required (brew install trivy)" >&2
    exit 2
fi

TRIVY_ARGS=(image --scanners secret --image-config-scanners secret --severity HIGH,CRITICAL)

echo "== Scanning release-candidate image: ${RC_IMAGE} =="
if ! trivy "${TRIVY_ARGS[@]}" --exit-code 1 "${RC_IMAGE}"; then
    echo "FAIL: ${RC_IMAGE} has a secret finding — see output above." >&2
    exit 1
fi
echo "OK: ${RC_IMAGE} has no secret finding."

echo
echo "== Proving the scan can fail: building and scanning the deliberately baited image =="

# Freshly generated every run, never tracked (.gitignore's *.pem/*.key rule) — removed
# unconditionally afterward regardless of how this script exits.
cleanup() { rm -f "${BAIT_KEY}"; }
trap cleanup EXIT

openssl genrsa -out "${BAIT_KEY}" 2048 >/dev/null 2>&1

docker build -f "${REPO_ROOT}/Dockerfile.secretbait" -t "${BAIT_IMAGE}" "${REPO_ROOT}"

set +e
trivy "${TRIVY_ARGS[@]}" --exit-code 1 "${BAIT_IMAGE}"
BAIT_SCAN_EXIT=$?
set -e

if [ "${BAIT_SCAN_EXIT}" -eq 0 ]; then
    echo "FAIL: the bait image (${BAIT_IMAGE}) produced NO secret finding — the negative" >&2
    echo "proof failed, meaning this scan cannot be trusted to catch anything (research.md R6)." >&2
    exit 1
fi

echo "OK: the bait image was correctly flagged — the scan is proven able to fail."
echo
echo "PASS: ${RC_IMAGE} is clean, and the scan is proven capable of detecting a secret."
