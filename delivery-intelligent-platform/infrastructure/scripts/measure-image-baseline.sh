#!/usr/bin/env bash
#
# FR-010: records image size (uncompressed + compressed, both labelled) and cold-start-to-ready
# timing (median and p90 over N runs, first discarded as warm-up) for the release-candidate
# image. Prints the raw numbers; docs/operations/container-image-baseline.md is written by hand
# from this output plus the conditions this script cannot know (host spec, Docker VM
# allocation, battery state, ...) — see
# specs/004-containerization/contracts/baseline-record.md.
#
# Measures the API container alone, with the database already healthy (contracts/
# baseline-record.md's headline metric): requires `docker compose up --wait sqlserver` to
# already be running so this script can attach to that same network rather than measuring a
# doomed connection attempt.
#
# Usage: measure-image-baseline.sh <release-candidate-image-tag> [runs]
set -euo pipefail

if [ $# -lt 1 ] || [ $# -gt 2 ]; then
    echo "usage: measure-image-baseline.sh <release-candidate-image-tag> [runs]" >&2
    exit 2
fi

RC_IMAGE="$1"
RUNS="${2:-10}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

SQLSERVER_CID=$(docker compose -f "${REPO_ROOT}/compose.yaml" ps -q sqlserver)
if [ -z "${SQLSERVER_CID}" ] || [ "$(docker inspect --format '{{.State.Health.Status}}' "${SQLSERVER_CID}" 2>/dev/null)" != "healthy" ]; then
    echo "sqlserver must already be running and healthy: run 'docker compose up --wait sqlserver' first" >&2
    exit 2
fi
COMPOSE_NETWORK=$(docker inspect --format '{{range $k, $v := .NetworkSettings.Networks}}{{$k}}{{end}}' "${SQLSERVER_CID}")
SA_PASSWORD=$(docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' "${SQLSERVER_CID}" | grep '^MSSQL_SA_PASSWORD=' | cut -d= -f2-)

echo "== Identification =="
echo "revision: $(git -C "${REPO_ROOT}" rev-parse HEAD)"
if [ -n "$(git -C "${REPO_ROOT}" status --porcelain)" ]; then
    echo "working tree: DIRTY — this record is not repeatable until committed"
else
    echo "working tree: clean"
fi
echo "image digest: $(docker image inspect --format '{{.Id}}' "${RC_IMAGE}")"

echo
echo "== Size =="
UNCOMPRESSED_BYTES=$(docker image inspect --format '{{.Size}}' "${RC_IMAGE}")
echo "uncompressed: ${UNCOMPRESSED_BYTES} bytes (docker image inspect --format '{{.Size}}')"

OCI_TAR="$(mktemp -t identity-api-oci).tar"
docker buildx build --load=false --output "type=oci,dest=${OCI_TAR}" -t "${RC_IMAGE}" "${REPO_ROOT}" >/dev/null
COMPRESSED_APPROX_BYTES=$(docker save "${RC_IMAGE}" | gzip -9 -c | wc -c | tr -d ' ')
echo "compressed (approximate, docker save | gzip -9 | wc -c): ${COMPRESSED_APPROX_BYTES} bytes"
echo "compressed (accurate): sum the manifest layer sizes in ${OCI_TAR} (index.json)"
rm -f "${OCI_TAR}"

echo
echo "== Largest layers =="
docker history --no-trunc "${RC_IMAGE}"

echo
echo "== Cold start to ready (${RUNS} runs, first discarded as warm-up) =="
TIMINGS=()
for i in $(seq 1 "${RUNS}"); do
    CID=$(docker run -d --rm --network "${COMPOSE_NETWORK}" -p 18080:8080 \
        -e ConnectionStrings__IdentityDb="Server=sqlserver;Database=IdentityDb;User Id=sa;Password=${SA_PASSWORD};Encrypt=True;TrustServerCertificate=True" \
        -e ASPNETCORE_ENVIRONMENT=Development \
        -e Https__RedirectionEnabled=false \
        -e AzureAd__Instance="https://login.microsoftonline.com/" \
        -e AzureAd__TenantId="baseline-tenant" \
        -e AzureAd__ClientId="baseline-client" \
        -e AzureAd__Audience="api://baseline" \
        "${RC_IMAGE}")

    START=$(date +%s.%N)
    ATTEMPTS=0
    until curl -fsS -o /dev/null "http://localhost:18080/health/ready" 2>/dev/null; do
        ATTEMPTS=$((ATTEMPTS + 1))
        if [ "${ATTEMPTS}" -gt 300 ]; then
            echo "run ${i}: never became ready after 60s — aborting" >&2
            docker logs "${CID}" >&2
            docker stop "${CID}" >/dev/null
            exit 1
        fi
        sleep 0.2
    done
    END=$(date +%s.%N)

    docker stop "${CID}" >/dev/null

    ELAPSED=$(echo "${END} - ${START}" | bc)
    if [ "$i" -eq 1 ]; then
        echo "run 1: ${ELAPSED}s (discarded as warm-up)"
    else
        echo "run ${i}: ${ELAPSED}s"
        TIMINGS+=("${ELAPSED}")
    fi
done

SORTED=($(printf '%s\n' "${TIMINGS[@]}" | sort -n))
COUNT=${#SORTED[@]}
MEDIAN_INDEX=$((COUNT / 2))
P90_INDEX=$(( (COUNT * 9) / 10 ))
[ "$P90_INDEX" -ge "$COUNT" ] && P90_INDEX=$((COUNT - 1))

echo
echo "median: ${SORTED[$MEDIAN_INDEX]}s"
echo "p90: ${SORTED[$P90_INDEX]}s"
echo "poll interval: 0.2s"
echo
echo "Write these numbers, plus the conditions this script cannot know (host spec, Docker VM" \
     "allocation, emulation, --cpus/--memory limits used, whether the database was already" \
     "healthy, ASPNETCORE_ENVIRONMENT, battery/thermal state), into" \
     "docs/operations/container-image-baseline.md per contracts/baseline-record.md."
