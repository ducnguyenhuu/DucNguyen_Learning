#!/usr/bin/env bash
#
# Idempotent seeding for the load test (specs/006-ci-cd/contracts/load-test.md): makes sure the
# automation identity belongs to tenants loadtest-01 … loadtest-20 and writes their IDs to a file
# that k6 reads. Safe to run on every pipeline — existing tenants are reused, and the
# Idempotency-Key makes a retried create return the original tenant instead of a duplicate.
#
# Usage:  BASE_URL=https://<frontdoor> TOKEN=<bearer> seed.sh <output-file>
# Output: JSON array of the 20 tenant IDs, ordered loadtest-01 … loadtest-20
set -euo pipefail

if [ $# -ne 1 ] || [ -z "${BASE_URL:-}" ] || [ -z "${TOKEN:-}" ]; then
    echo "usage: BASE_URL=<url> TOKEN=<bearer> seed.sh <output-file>" >&2
    exit 2
fi

OUT="$1"
COUNT=20

existing=$(curl -fsS -H "Authorization: Bearer ${TOKEN}" "${BASE_URL}/tenants")

ids=()
for i in $(seq 1 "${COUNT}"); do
    name=$(printf 'loadtest-%02d' "${i}")
    id=$(jq -r --arg n "${name}" '[.[] | select(.displayName == $n)][0].id // empty' <<<"${existing}")

    if [ -z "${id}" ]; then
        id=$(curl -fsS -X POST "${BASE_URL}/tenants" \
            -H "Authorization: Bearer ${TOKEN}" \
            -H "Content-Type: application/json" \
            -H "Idempotency-Key: seed-${name}" \
            -d "{\"displayName\":\"${name}\"}" | jq -r '.id')
        echo "created ${name}"
    fi
    ids+=("${id}")
done

printf '%s\n' "${ids[@]}" | jq -R . | jq -s . >"${OUT}"
echo "wrote ${#ids[@]} tenant IDs to ${OUT}"
