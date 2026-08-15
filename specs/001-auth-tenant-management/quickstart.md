# Quickstart: Tenancy (S2)

**Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md) · **Contracts**: [contracts/openapi.yaml](contracts/openapi.yaml)

Gets the slice running and verified **on a development machine**. No Azure subscription is
required — that dependency begins at S6.

---

## Prerequisites

| Requirement | Notes |
|---|---|
| .NET 10 SDK | `dotnet --version` → 10.0.x. Confirmed present: 10.0.105 |
| Docker Desktop or OrbStack | Needs **≥4 GB** to the VM — SQL Server wants ~2 GB, and it runs emulated on Apple Silicon |
| An Entra ID tenant with app-registration rights | Free tier is sufficient. No subscription, no deployed resources |
| `gitleaks` | For the SC-008 history scan |

**Apple Silicon note** (this machine is Darwin ARM64): enable Docker Desktop →
Settings → General → *Use Rosetta for x86/amd64 emulation*. SQL Server has no native arm64
build, so expect 20–60 s container startup. Do not switch to `mssql/server:2025-latest` —
2025 RTM requires AVX instructions that Rosetta does not implement and crashes on startup
(fixed only in `2025-CU1-ubuntu-24.04`).

---

## 1. Entra app registrations

**Run the script. Do not click through the portal.**

```bash
az login --tenant <your-tenant-id>
./infrastructure/scripts/create-entra-app-registrations.sh
```

It is idempotent, so re-running is safe. It prints the tenant id, API client id, and dev
client id you need in step 2.

Portal instructions used to live here and were deliberately replaced. ADR-012 and Principle X
require environments to be reproducible from code, and the `azure-architecture` skill states
it plainly: **anything that exists only because someone clicked it is a defect.** Terraform
arrives in S6, so a small committed script is the same accepted exception as the Terraform
state bootstrap — and at S6 it becomes the specification for the `azuread_application`
resources rather than something to reverse-engineer from a portal.

**Tenant choice matters more than it looks.** Use a tenant you will still control in several
years. A university or employer tenant may block app registration outright, and if the account
is ever revoked it takes the registrations *and* the `(EntraTenantId, EntraObjectId)` identity
mapping stored against every `User` row with it.

What the script creates, and the two details worth knowing:

| | API registration | Dev client registration |
|---|---|---|
| Purpose | The protected resource | Obtaining test tokens |
| Audience | Single tenant | Single tenant |
| Redirect URI | **None** — APIs do not redirect | `http://localhost` |
| Client secret | **None** | **None** |
| Exposes | scope `access_as_user`, `api://{clientId}` | — |

- **Neither registration has a client secret.** A token-validating API holds no credential, and
  a public client must not hold one (it uses PKCE). So there is nothing here to leak, rotate,
  or scan for — that is a design property, not a gap in the setup.
- **`requestedAccessTokenVersion: 2`** is set by the script and is easy to miss by hand. v1
  tokens use a different issuer format and omit `preferred_username`, so claim-reading code
  silently behaves differently.

---

## 2. Configuration

```bash
cd src/Tenancy/Tenancy.Api
dotnet user-secrets init
dotnet user-secrets set "AzureAd:TenantId"  "<entra-tenant-guid>"
dotnet user-secrets set "AzureAd:ClientId"  "<api-client-id>"
dotnet user-secrets set "ConnectionStrings:TenancyDb" \
  "Server=localhost,1433;Database=Tenancy;User Id=sa;Password=<local-dev-password>;TrustServerCertificate=true"
```

Neither the tenant id nor the client id is a secret, but User Secrets keeps them out of the
working tree anyway — and `appsettings.Development.json` is `.gitignore`d, so committing them
by accident is harder than not (FR-026).

**The API holds no client secret at all.** It only *validates* tokens; it never acquires
them. That is a design property worth noticing rather than a configuration shortcut — there
is no credential here to leak, rotate, or scan for.

---

## 3. Database and migrations

```bash
docker run -d --name tenancy-sql \
  -e "ACCEPT_EULA=Y" -e "MSSQL_SA_PASSWORD=<local-dev-password>" \
  -p 1433:1433 mcr.microsoft.com/mssql/server:2022-latest

dotnet ef database update -p src/Tenancy/Tenancy.Infrastructure -s src/Tenancy/Tenancy.Api
```

Migrations also run automatically at startup in Development. That shortcut is
**Development-only by design** — Microsoft's guidance is explicit that `Migrate()` at startup
is not acceptable in production (concurrent instances, the app needing DDL rights, no
rollback, no SQL review). The production path is a migration bundle run with a separate
DDL-privileged identity, and it belongs to S6/S7. See [research.md](research.md) R8.

Before committing any migration, read the SQL it generates:

```bash
dotnet ef migrations script -p src/Tenancy/Tenancy.Infrastructure -s src/Tenancy/Tenancy.Api
```

A rename can come out as a drop, and the diff is the only place that is visible.

---

## 4. Run

```bash
dotnet run --project src/Tenancy/Tenancy.Api
# → https://localhost:7001
```

`SC-007` is satisfied when this works against an **empty** database with no manual step.

---

## 5. Get a token

```bash
az login --tenant <entra-tenant-guid>
TOKEN=$(az account get-access-token --resource api://<api-client-id> --query accessToken -o tsv)
```

Inspect it once (paste into <https://jwt.ms>) and confirm `ver: 2.0`, plus `oid` and `tid`
present. **Record the observed payload as a test fixture.** Nothing in the test suite proves
Entra actually issues the claims the code reads — only a real token does, and only once per
claim-shape change.

---

## 6. Walk the acceptance scenarios

Proves Story 1 end to end. `SC-001` measures this path — time it.

```bash
API=https://localhost:7001
AUTH="Authorization: Bearer $TOKEN"

# Create a tenant (FR-005, FR-020)
curl -sS -X POST $API/tenants -H "$AUTH" \
  -H "Idempotency-Key: $(uuidgen)" -H "Content-Type: application/json" \
  -d '{"displayName":"Acme Engineering"}' -D - | tee /tmp/tenant.txt
# → 201, Location, ETag. Creator is the first Administrator.

TENANT=$(jq -r .id < <(tail -1 /tmp/tenant.txt))

# List my tenants (FR-010) — one of only three non-tenant-scoped operations
curl -sS $API/tenants -H "$AUTH"

# Read it (FR-006)
curl -sS $API/tenants/$TENANT -H "$AUTH" -D -

# Rename it — If-Match required (FR-021)
ETAG=$(curl -sS -D - -o /dev/null $API/tenants/$TENANT -H "$AUTH" | grep -i '^etag:' | cut -d' ' -f2 | tr -d '\r')
curl -sS -X PATCH $API/tenants/$TENANT -H "$AUTH" -H "If-Match: $ETAG" \
  -H "Content-Type: application/merge-patch+json" -d '{"displayName":"Acme Engineering Ltd"}'

# Invite a colleague (FR-011) — token returned once, never stored
curl -sS -X POST $API/tenants/$TENANT/invitations -H "$AUTH" \
  -H "Idempotency-Key: $(uuidgen)" -H "Content-Type: application/json" \
  -d '{"email":"colleague@example.com","role":"Member"}'

# Accept as the invited identity (FR-012) — the second of the three unscoped operations
curl -sS -X POST $API/invitations/<token>/accept -H "Authorization: Bearer $COLLEAGUE_TOKEN"
```

### The refusals matter more than the successes

Every one of these must fail, and fail in the *specific* way named:

```bash
# No token → 401, no data disclosed (FR-002)
curl -sS -o /dev/null -w '%{http_code}\n' $API/tenants/$TENANT

# Someone else's tenant → 404, NOT 403 (FR-009)
#   A 403 here would confirm the tenant exists. This is the check that matters most.
curl -sS -o /dev/null -w '%{http_code}\n' $API/tenants/<other-tenants-id> -H "$AUTH"

# Non-administrator inviting → 403 (FR-018) — member, wrong role
curl -sS -o /dev/null -w '%{http_code}\n' -X POST $API/tenants/$TENANT/invitations \
  -H "Authorization: Bearer $READER_TOKEN" -H "Idempotency-Key: $(uuidgen)" \
  -H "Content-Type: application/json" -d '{"email":"x@example.com","role":"Reader"}'

# Remove the only administrator → 409 (FR-015)
curl -sS -o /dev/null -w '%{http_code}\n' -X DELETE \
  $API/tenants/$TENANT/members/<sole-admin-user-id> -H "$AUTH" -H "If-Match: $ETAG"

# Replay the same Idempotency-Key → 201 again with the SAME body, not 200 (FR-020)
# Same key, DIFFERENT body → 422
```

**404-not-403 for a non-member is the single most important assertion in the slice.** Getting
it backwards makes every tenant enumerable by identifier substitution.

---

## 7. Run the tests

```bash
dotnet test
```

First run pulls the SQL Server image and starts it emulated — allow a couple of minutes and
set CI timeouts accordingly. One container serves the whole assembly (xUnit v3
`AssemblyFixture`); Respawn resets state between tests.

`SC-006` requires the full suite unattended in **under 5 minutes**. Measure it now and record
the number — this is the baseline that S3 must keep.

---

## 8. Secret scan — including history

```bash
gitleaks detect --no-git=false --verbose
```

`SC-008` and roadmap S2's *Done when* both require scanning **history**, not just the working
tree. A secret committed once is compromised even after removal; the remedy is rotation, not
deletion. Pipeline enforcement arrives in S7 — until then this is a manual step, so run it
before every push.

---

## Troubleshooting

| Symptom | Cause |
|---|---|
| Container exits with AVX assertion failures | `mssql/server:2025-RTM` on Apple Silicon. Use `2022-latest` or `2025-CU1-ubuntu-24.04`. |
| SQL container starts then dies silently | Docker VM memory below ~2 GB. |
| `401` with a token that looks valid | Audience mismatch. The token must be for `api://{clientId}`, not Graph. Check `aud` at jwt.ms. |
| Tests pass but the real API returns `403` | Claim-name mismatch between production and the test auth handler — the classic symptom of `MapInboundClaims` disagreement. Both must read `oid`/`tid`/`scp`. |
| `401` tests suddenly pass when they should fail | The test auth handler is succeeding unconditionally. It must return `AuthenticateResult.NoResult()` when no `Authorization` header is present. |
| Cross-tenant test passes suspiciously easily | Confirm it was ever **red**. A green isolation test that could never fail proves nothing (`idea.md` §59.2). |
