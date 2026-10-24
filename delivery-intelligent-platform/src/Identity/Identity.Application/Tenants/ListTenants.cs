using Identity.Application.Abstractions;
using Identity.Domain.Abstractions;
using Identity.Domain.Tenants;

namespace Identity.Application.Tenants;

/// <summary>
/// Lists every <see cref="Tenant"/> the calling user belongs to, for <c>GET /tenants</c>
/// (ADR-017 exception 2).
/// </summary>
/// <remarks>
/// First fetches the caller's active memberships across every tenant via T037's audited
/// <see cref="IMembershipDirectory"/> (the only sanctioned cross-tenant bypass in the codebase),
/// then fetches the corresponding <see cref="Tenant"/> rows via
/// <see cref="ITenantRepository.GetManyByIdsAsync"/>. That second lookup needs no bypass of its
/// own: <see cref="Tenant"/> does not implement <see cref="ITenantOwned"/> (confirmed by
/// inspection of <c>Tenant.cs</c>, unlike <see cref="Domain.Memberships.Membership"/>, which
/// does), so <c>IdentityDbContext</c>'s <c>"TenantFilter"</c> global query filter — applied only to
/// <see cref="ITenantOwned"/> entity types — was never applied to <see cref="Tenant"/> reads in
/// the first place. Only the <see cref="Domain.Memberships.Membership"/> lookup needed T037's
/// audited bypass.
/// </remarks>
public class ListTenants
{
    private readonly IMembershipDirectory _membershipDirectory;
    private readonly ITenantRepository _tenantRepository;

    public ListTenants(IMembershipDirectory membershipDirectory, ITenantRepository tenantRepository)
    {
        _membershipDirectory = membershipDirectory;
        _tenantRepository = tenantRepository;
    }

    public async Task<IReadOnlyList<Tenant>> ExecuteAsync(UserId userId, CancellationToken ct)
    {
        var memberships = await _membershipDirectory.GetMembershipsForUserAsync(userId, ct);
        if (memberships.Count == 0)
        {
            return [];
        }

        var tenantIds = memberships.Select(m => m.TenantId).Distinct().ToList();

        return await _tenantRepository.GetManyByIdsAsync(tenantIds, ct);
    }
}
