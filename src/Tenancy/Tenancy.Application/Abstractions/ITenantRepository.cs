using Tenancy.Domain.Abstractions;
using Tenancy.Domain.Tenants;

namespace Tenancy.Application.Abstractions;

/// <summary>
/// Repository port for the read/rename-shaped operations <c>GetTenant</c> (T055),
/// <c>RenameTenant</c> (T055), and <c>ListTenants</c> (T055) need against the
/// <see cref="Tenant"/> aggregate.
/// </summary>
/// <remarks>
/// <para>
/// <b>One port, not three:</b> unlike <see cref="ICreateTenantRepository"/> (T054), which exposes
/// exactly one intention-revealing "create tenant + its first membership atomically" operation,
/// <c>GetTenant</c>, <c>RenameTenant</c>, and <c>ListTenants</c> are three thin, single-aggregate
/// CRUD-shaped reads/writes against the same <see cref="Tenant"/> table with no cross-aggregate
/// choreography between them. Three separate one-method interfaces
/// (<c>IGetTenantRepository</c>/<c>IRenameTenantRepository</c>/<c>IListTenantsRepository</c>)
/// would be near-identical ceremony wrapping the same underlying table access, and
/// <c>RenameTenant</c> in particular needs both "get" and "save" in the same use case body — so a
/// single small port covering the shared shape (get one, get many, save) is the less speculative,
/// less repetitive choice here. This does not fold in <see cref="ICreateTenantRepository"/>'s
/// two-aggregate create operation: that one's atomicity contract (tenant + membership, one
/// transaction) is a genuinely different shape and stays on its own port per T054's precedent.
/// </para>
/// <para>
/// <b>No bypass needed for <see cref="Tenant"/> reads:</b> <see cref="Tenant"/> does not implement
/// <see cref="ITenantOwned"/> (confirmed by inspection — <c>Tenant.cs</c> has no such interface,
/// unlike <see cref="Domain.Memberships.Membership"/>, which does), so
/// <c>TenancyDbContext</c>'s <c>"TenantFilter"</c> global query filter — which is only ever
/// applied to entity types implementing <see cref="ITenantOwned"/> (see
/// <c>TenancyDbContext.OnModelCreating</c>) — was never applied to <see cref="Tenant"/> in the
/// first place. <see cref="GetManyByIdsAsync"/>, used by <c>ListTenants</c> to fetch tenants
/// across every tenant the caller belongs to, therefore needs no
/// <c>IgnoreQueryFilters</c>/bypass helper of its own — there is nothing to bypass.
/// </para>
/// </remarks>
public interface ITenantRepository
{
    /// <summary>
    /// Returns the single <see cref="Tenant"/> scoped by the ambient
    /// <c>TenancyDbContext.CurrentTenantId</c>, or <c>null</c> if none exists (which would
    /// indicate a bug further upstream, since by the time a use case runs, the caller's
    /// membership in this tenant has already been verified).
    /// </summary>
    Task<Tenant?> GetCurrentAsync(CancellationToken ct);

    /// <summary>
    /// Returns every <see cref="Tenant"/> whose <see cref="TenantId"/> is in
    /// <paramref name="tenantIds"/>, regardless of the ambient
    /// <c>TenancyDbContext.CurrentTenantId</c> (safe/necessary because <see cref="Tenant"/> is not
    /// <see cref="ITenantOwned"/> and is therefore never subject to the tenant-scoping filter).
    /// </summary>
    Task<IReadOnlyList<Tenant>> GetManyByIdsAsync(IReadOnlyCollection<TenantId> tenantIds, CancellationToken ct);

    /// <summary>
    /// Persists changes made to a previously-fetched <see cref="Tenant"/> (e.g. via
    /// <see cref="Tenant.Rename"/>). Implementations are expected to call
    /// <c>SaveChangesAsync</c>, not merely stage the change.
    /// </summary>
    Task SaveAsync(Tenant tenant, CancellationToken ct);
}
