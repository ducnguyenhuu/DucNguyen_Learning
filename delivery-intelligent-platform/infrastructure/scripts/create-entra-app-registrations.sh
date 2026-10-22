#!/usr/bin/env bash
#
# Creates the two Entra ID app registrations roadmap S2 needs.
#
# WHY THIS IS A SCRIPT AND NOT PORTAL INSTRUCTIONS
# ------------------------------------------------
# ADR-012 and Constitution Principle X require environments to be reproducible from
# code. The `azure-architecture` skill puts it bluntly: anything that exists only
# because someone clicked it is a defect. Terraform arrives in S6, so this is the
# same accepted exception as the Terraform state bootstrap — a small, committed,
# idempotent script.
#
# At S6 this becomes the specification for `azuread_application` resources. Until
# then, running this is reproducible; clicking through the portal is not.
#
# APP ROLES ARE NOT THIS SCRIPT'S
# -------------------------------
# The app role `Tenancy.Automation.Member` (ADR-022) is owned by
# infrastructure/terraform/persistent/app-role.tf. This script only PATCHes the
# `api` property, so it leaves `appRoles` alone — keep it that way: never add an
# `appRoles` entry to a PATCH body here, because Graph replaces the whole list
# and would delete the role Terraform manages.
#
# WHAT IT CREATES
# ---------------
#   1. API registration      — the thing being protected. Single tenant.
#                              No redirect URI (APIs do not redirect).
#                              NO CLIENT SECRET: a token-validating API holds no
#                              credential, so there is nothing here to leak or
#                              rotate. That is a design property, not an omission.
#                              Exposes scope `access_as_user`.
#                              requestedAccessTokenVersion = 2 — without this you
#                              get v1 tokens with a different issuer format and no
#                              `preferred_username`, and claim-reading code silently
#                              behaves differently (research.md R2).
#
#   2. Dev client registration — for obtaining test tokens. Public client, PKCE,
#                              redirect `http://localhost`. Also no secret: public
#                              clients must not hold one.
#
# Neither app gets a secret. If a future change needs one, that is a decision worth
# arguing about, not a convenience.
#
# IDEMPOTENT: safe to re-run. Existing registrations are reused, not duplicated.
#
# Usage:
#   az login --tenant <your-tenant-id>
#   ./infrastructure/scripts/create-entra-app-registrations.sh
#
set -euo pipefail

API_APP_NAME="${API_APP_NAME:-Delivery Intelligence API}"
CLIENT_APP_NAME="${CLIENT_APP_NAME:-Delivery Intelligence Dev Client}"
SCOPE_VALUE="access_as_user"

die() { printf '\n\033[31mERROR:\033[0m %s\n' "$*" >&2; exit 1; }
step() { printf '\n\033[36m▶ %s\033[0m\n' "$*"; }
note() { printf '  %s\n' "$*"; }

command -v az >/dev/null || die "Azure CLI not found. Install it first."

step "Checking sign-in"
ACCOUNT_JSON=$(az account show -o json 2>/dev/null) \
  || die "Not signed in. Run: az login --tenant <tenant-id>"

TENANT_ID=$(printf '%s' "$ACCOUNT_JSON" | python3 -c 'import json,sys;print(json.load(sys.stdin)["tenantId"])')
UPN=$(printf '%s' "$ACCOUNT_JSON" | python3 -c 'import json,sys;print(json.load(sys.stdin)["user"]["name"])')
note "Tenant: $TENANT_ID"
note "User:   $UPN"

# Verify the Graph token actually works. `az account show` reads a local cache and
# succeeds even when the refresh token has expired, so it proves nothing on its own.
az rest --method GET --url "https://graph.microsoft.com/v1.0/me?\$select=id" -o none 2>/dev/null \
  || die "Microsoft Graph rejected the cached token (it has probably expired).
       Run: az logout && az login --tenant $TENANT_ID"

# ---------------------------------------------------------------------------
# 1. API registration
# ---------------------------------------------------------------------------
step "API registration: $API_APP_NAME"

API_OBJECT_ID=$(az ad app list --filter "displayName eq '$API_APP_NAME'" \
                  --query "[0].id" -o tsv --only-show-errors 2>/dev/null || true)

if [[ -n "$API_OBJECT_ID" && "$API_OBJECT_ID" != "None" ]]; then
  note "Already exists — reusing (object id $API_OBJECT_ID)"
else
  API_OBJECT_ID=$(az ad app create \
      --display-name "$API_APP_NAME" \
      --sign-in-audience AzureADMyOrg \
      --query id -o tsv --only-show-errors)
  note "Created (object id $API_OBJECT_ID)"
fi

API_APP_ID=$(az ad app show --id "$API_OBJECT_ID" --query appId -o tsv --only-show-errors)
note "Client (application) id: $API_APP_ID"

# Reuse the existing scope id if present — changing it would invalidate any consent
# already granted, which is a confusing failure to debug.
SCOPE_ID=$(az ad app show --id "$API_OBJECT_ID" \
             --query "api.oauth2PermissionScopes[?value=='$SCOPE_VALUE'].id | [0]" \
             -o tsv --only-show-errors 2>/dev/null || true)
if [[ -z "$SCOPE_ID" || "$SCOPE_ID" == "None" ]]; then
  SCOPE_ID=$(python3 -c 'import uuid;print(uuid.uuid4())')
  note "Scope '$SCOPE_VALUE' will be created with id $SCOPE_ID"
else
  note "Scope '$SCOPE_VALUE' already exists (id $SCOPE_ID) — preserving it"
fi

step "Configuring API: identifier URI, v2 tokens, exposed scope"
PATCH_BODY=$(python3 - "$API_APP_ID" "$SCOPE_ID" "$SCOPE_VALUE" <<'PY'
import json, sys
app_id, scope_id, scope_value = sys.argv[1], sys.argv[2], sys.argv[3]
print(json.dumps({
    "identifierUris": [f"api://{app_id}"],
    "api": {
        # v2 tokens. See the header comment — this one is easy to miss and
        # changes the issuer format and available claims.
        "requestedAccessTokenVersion": 2,
        "oauth2PermissionScopes": [{
            "id": scope_id,
            "value": scope_value,
            "type": "User",
            "isEnabled": True,
            "adminConsentDisplayName": "Access the Delivery Intelligence API",
            "adminConsentDescription":
                "Allows the application to call the Delivery Intelligence API as the signed-in user.",
            "userConsentDisplayName": "Access the API on your behalf",
            "userConsentDescription":
                "Allows the application to call the Delivery Intelligence API on your behalf.",
        }],
    },
}))
PY
)
az rest --method PATCH \
        --url "https://graph.microsoft.com/v1.0/applications/$API_OBJECT_ID" \
        --headers "Content-Type=application/json" \
        --body "$PATCH_BODY" -o none
note "api://$API_APP_ID  ·  scope $SCOPE_VALUE  ·  access token v2"

# A service principal is required before consent can be granted against this API.
az ad sp show --id "$API_APP_ID" -o none --only-show-errors 2>/dev/null \
  || { az ad sp create --id "$API_APP_ID" -o none --only-show-errors; note "Service principal created"; }

# Pre-authorize the Azure CLI's own first-party app as a known client of this API.
# Without this, `az account get-access-token --resource api://<id>` fails with
# AADSTS650057 ("Invalid resource") — the CLI's app (a Microsoft first-party app,
# not one we created) has no standing permission on a brand-new custom API. This is
# what lets you fetch test tokens with plain `az` commands, per quickstart.md §5.
AZURE_CLI_APP_ID="04b07795-8ddb-461a-bbee-02f9e1bf7b46"
az rest --method PATCH \
        --url "https://graph.microsoft.com/v1.0/applications/$API_OBJECT_ID" \
        --headers "Content-Type=application/json" \
        --body "{\"api\":{\"preAuthorizedApplications\":[{\"appId\":\"$AZURE_CLI_APP_ID\",\"delegatedPermissionIds\":[\"$SCOPE_ID\"]}]}}" \
        -o none
note "Azure CLI pre-authorized as a known client (needed for 'az account get-access-token')"

# ---------------------------------------------------------------------------
# 2. Dev client registration
# ---------------------------------------------------------------------------
step "Dev client registration: $CLIENT_APP_NAME"

CLIENT_OBJECT_ID=$(az ad app list --filter "displayName eq '$CLIENT_APP_NAME'" \
                     --query "[0].id" -o tsv --only-show-errors 2>/dev/null || true)

if [[ -n "$CLIENT_OBJECT_ID" && "$CLIENT_OBJECT_ID" != "None" ]]; then
  note "Already exists — reusing (object id $CLIENT_OBJECT_ID)"
else
  CLIENT_OBJECT_ID=$(az ad app create \
      --display-name "$CLIENT_APP_NAME" \
      --sign-in-audience AzureADMyOrg \
      --is-fallback-public-client true \
      --public-client-redirect-uris "http://localhost" \
      --query id -o tsv --only-show-errors)
  note "Created (object id $CLIENT_OBJECT_ID)"
fi

CLIENT_APP_ID=$(az ad app show --id "$CLIENT_OBJECT_ID" --query appId -o tsv --only-show-errors)
note "Client (application) id: $CLIENT_APP_ID"

az ad sp show --id "$CLIENT_APP_ID" -o none --only-show-errors 2>/dev/null \
  || { az ad sp create --id "$CLIENT_APP_ID" -o none --only-show-errors; note "Service principal created"; }

step "Granting the dev client delegated access to the API"
az ad app permission add --id "$CLIENT_APP_ID" \
    --api "$API_APP_ID" --api-permissions "$SCOPE_ID=Scope" \
    --only-show-errors 2>/dev/null || note "Permission already present"

# Pre-consent so local token acquisition does not prompt. Needs privileges to consent
# in this tenant; harmless if it fails — you will simply consent once, interactively.
if az ad app permission grant --id "$CLIENT_APP_ID" --api "$API_APP_ID" \
       --scope "$SCOPE_VALUE" -o none --only-show-errors 2>/dev/null; then
  note "Admin consent granted"
else
  note "Could not pre-grant consent — you will be prompted once on first sign-in. Not a problem."
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
cat <<EOF

$(printf '\033[32m✓ Done.\033[0m') Neither registration has a client secret — by design.

  Tenant id            $TENANT_ID
  API client id        $API_APP_ID
  Application ID URI   api://$API_APP_ID
  Exposed scope        $SCOPE_VALUE
  Dev client id        $CLIENT_APP_ID

Configure the API (from the repo root, once src/ exists):

  cd src/Tenancy/Tenancy.Api
  dotnet user-secrets init
  dotnet user-secrets set "AzureAd:TenantId" "$TENANT_ID"
  dotnet user-secrets set "AzureAd:ClientId" "$API_APP_ID"

Get a token to call the API:

  az account get-access-token --resource "api://$API_APP_ID" --query accessToken -o tsv

Paste that token into https://jwt.ms once and confirm \`ver: 2.0\`, \`oid\`, and \`tid\`
are present. Record the payload as a test fixture — nothing in the test suite proves
Entra actually issues the claims the code reads. Only a real token does.

EOF
