# Shared by session-up.sh and session-down.sh. Source it; do not run it.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERRAFORM_DIR="${SCRIPT_DIR}/../terraform"
STATE_RG="rg-dip-tfstate"
PERSISTENT_RG="rg-dip-persistent"

require_azure_login() {
    az account show >/dev/null 2>&1 || { echo "Not logged in: run 'az login' first." >&2; exit 2; }
    echo "Subscription: $(az account show --query '[name,id]' -o tsv | tr '\t' ' ')"
}

require_tfvars() {
    [ -f "${TERRAFORM_DIR}/dev.tfvars" ] \
        || { echo "Missing infrastructure/terraform/dev.tfvars (copy dev.tfvars.example)." >&2; exit 2; }
}

# The S6 resource group name, read from dev.tfvars so the scripts never disagree with Terraform.
dev_resource_group() {
    local rg
    rg=$(sed -n 's/^resource_group_name[[:space:]]*=[[:space:]]*"\(.*\)"/\1/p' "${TERRAFORM_DIR}/dev.tfvars")
    echo "${rg:-rg-dip-dev}"
}

# Same deterministic name bootstrap-state.sh generates, unless STATE_STORAGE_ACCOUNT overrides it.
state_storage_account() {
    local sub
    sub=$(az account show --query id -o tsv)
    echo "${STATE_STORAGE_ACCOUNT:-stdiptfstate$(echo "${sub}" | tr -d '-' | cut -c1-8)}"
}

terraform_init() {
    terraform -chdir="${TERRAFORM_DIR}" init -input=false \
        -backend-config="resource_group_name=${STATE_RG}" \
        -backend-config="storage_account_name=$(state_storage_account)" \
        -backend-config="container_name=tfstate" \
        -backend-config="key=dev.tfstate" >/dev/null
}
