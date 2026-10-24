using Identity.Domain.Abstractions;
using Identity.Domain.Memberships;
using Identity.Domain.Tenants;

namespace Identity.Application.Abstractions;

/// <summary>
/// Repository port for the single operation <c>Tenants.CreateTenant</c> (T054) needs: persisting
/// a newly created <see cref="Tenant"/> together with its creator's <see cref="Membership"/> in
/// one transaction.
/// </summary>
/// <remarks>
/// <para>
/// This is the second repository port in the codebase, following the minimal, per-use-case
/// pattern established by <see cref="IUserRepository"/> (T036) rather than a general-purpose
/// <c>ITenantRepository</c>/unit-of-work abstraction — there is exactly one write scenario that
/// needs this ("new tenant + its first Administrator membership, atomically"), and no other
/// current use case needs a bare "add a Tenant" or "add a Membership" operation on its own, so a
/// broader surface would be speculative (YAGNI). Later use cases that need different
/// tenant/membership persistence shapes should get their own minimal port, following this same
/// precedent, rather than this one growing extra methods.
/// </para>
/// <para>
/// Deliberately not named <c>IIdentityUnitOfWork</c>: that name would suggest a general
/// save-everything-in-the-context abstraction, which this explicitly is not — it exposes exactly
/// one intention-revealing operation.
/// </para>
/// </remarks>
public interface ICreateTenantRepository
{
    /// <summary>
    /// Persists the given <paramref name="tenant"/> and <paramref name="administratorMembership"/>
    /// together in a single <c>SaveChangesAsync</c> call (implementations are expected to call
    /// <c>SaveChangesAsync</c>, not merely stage the additions).
    /// </summary>
    Task AddAsync(Tenant tenant, Membership administratorMembership, CancellationToken ct);
}
