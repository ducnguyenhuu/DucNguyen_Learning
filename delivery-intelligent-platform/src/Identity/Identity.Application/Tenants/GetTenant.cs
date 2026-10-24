using Identity.Application.Abstractions;
using Identity.Domain.Tenants;

namespace Identity.Application.Tenants;

/// <summary>
/// Reads the single <see cref="Tenant"/> the caller is currently scoped to, for
/// <c>GET /tenants/{tenantId}</c> ("Any active member, any role.").
/// </summary>
/// <remarks>
/// This use case does <b>not</b> re-check membership — by the time it runs, T035's middleware has
/// already resolved <c>IdentityDbContext.CurrentTenantId</c> to the requested tenant and verified
/// the caller is an active member of it. There is deliberately no <c>TenantId</c> parameter here:
/// the ambient <c>CurrentTenantId</c> the read-side <c>"TenantFilter"</c> scopes to IS the
/// resolved tenant, so <see cref="ITenantRepository.GetCurrentAsync"/> returns exactly the one row
/// needed (or <c>null</c>, which would indicate a bug further upstream — not this use case's
/// concern).
/// </remarks>
public class GetTenant
{
    private readonly ITenantRepository _tenantRepository;

    public GetTenant(ITenantRepository tenantRepository)
    {
        _tenantRepository = tenantRepository;
    }

    public Task<Tenant?> ExecuteAsync(CancellationToken ct)
    {
        return _tenantRepository.GetCurrentAsync(ct);
    }
}
