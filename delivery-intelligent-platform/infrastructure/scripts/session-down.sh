#!/usr/bin/env bash
#
# Ends a working session: destroys the S6 dev environment and then PROVES nothing billable is
# left. Exits non-zero if anything remains, so a forgotten resource is never silent.
#
# Keeps (they cost cents or nothing): the Terraform state storage (rg-dip-tfstate) and the
# pipeline identities (rg-dip-persistent).
#
# Usage: session-down.sh [--yes]     (--yes skips the destroy confirmation)
set -euo pipefail

# shellcheck source=_session-lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_session-lib.sh"

AUTO=()
[ "${1:-}" = "--yes" ] && AUTO=(-auto-approve)

require_azure_login
require_tfvars
RG="$(dev_resource_group)"

# Variables Terraform insists on even when destroying; the values are irrelevant here.
export TF_VAR_new_relic_licence_key="${TF_VAR_new_relic_licence_key:-destroy-placeholder}"

echo "== 1/3 terraform destroy (${RG})"
terraform_init
terraform -chdir="${TERRAFORM_DIR}" destroy -var-file=dev.tfvars -var "api_image_tag=destroy" "${AUTO[@]}"

echo "== 2/3 purge the soft-deleted Key Vault (otherwise the next build hits a name clash)"
for vault in $(az keyvault list-deleted --query "[].name" -o tsv 2>/dev/null | grep '^kv-dip-' || true); do
    echo "purging ${vault}"
    az keyvault purge --name "${vault}" --only-show-errors || echo "could not purge ${vault} (purge protection?)" >&2
done

echo "== 3/3 verify nothing is left"
left=0

if [ "$(az group exists --name "${RG}")" = "true" ]; then
    echo "STILL EXISTS: resource group ${RG}"
    az resource list --resource-group "${RG}" --query "[].{name:name,type:type}" -o table
    left=1
fi

# Container Apps creates a managed ME_* group for its environment; it should vanish too.
extra=$(az group list --query "[?starts_with(name,'ME_cae-dip')].name" -o tsv)
if [ -n "${extra}" ]; then
    echo "STILL EXISTS: managed group(s): ${extra}"
    left=1
fi

deleted=$(az keyvault list-deleted --query "[?starts_with(name,'kv-dip-')].name" -o tsv 2>/dev/null || true)
if [ -n "${deleted}" ]; then
    echo "NOTE: soft-deleted Key Vault(s) still reserved: ${deleted} (free, but they block the name)"
fi

if [ "${left}" -eq 0 ]; then
    echo
    echo "OK: ${RG} is gone. Nothing billable is left (state storage and pipeline identities are kept, they are ~free)."
else
    echo
    echo "LEFTOVERS FOUND — these may still be billing. Fix, then re-run this script." >&2
    exit 1
fi
