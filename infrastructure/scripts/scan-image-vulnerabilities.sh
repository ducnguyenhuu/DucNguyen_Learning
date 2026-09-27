#!/usr/bin/env bash
#
# FR-012: repeatable image vulnerability scan of the release-candidate image at a fixed
# HIGH/CRITICAL severity threshold, every run. A separate script and a separate exit code
# from scan-image-secrets.sh, so a CVE finding and a secret finding are never conflated
# (see specs/004-containerization/contracts/container-image.md's "Vulnerability guarantee").
# The severity threshold is fixed, not configurable — deciding what happens on a finding
# (waiver process, exception review) is a CI-gate policy question deferred to S7; this script
# only needs to run and report against one fixed bar every time.
#
# Usage: scan-image-vulnerabilities.sh <release-candidate-image-tag>
set -euo pipefail

if [ $# -ne 1 ]; then
    echo "usage: scan-image-vulnerabilities.sh <release-candidate-image-tag>" >&2
    exit 2
fi

RC_IMAGE="$1"

if ! command -v trivy >/dev/null 2>&1; then
    echo "trivy is required (brew install trivy)" >&2
    exit 2
fi

echo "== Scanning release-candidate image for vulnerabilities: ${RC_IMAGE} =="
if ! trivy image --scanners vuln --severity HIGH,CRITICAL --exit-code 1 "${RC_IMAGE}"; then
    echo "FAIL: ${RC_IMAGE} has an unresolved HIGH or CRITICAL vulnerability finding." >&2
    exit 1
fi

echo "PASS: ${RC_IMAGE} has zero unresolved HIGH or CRITICAL vulnerability findings."
