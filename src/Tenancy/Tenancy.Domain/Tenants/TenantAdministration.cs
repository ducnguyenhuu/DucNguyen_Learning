using Tenancy.Domain.Abstractions;
using Tenancy.Domain.Memberships;

namespace Tenancy.Domain.Tenants;

/// <summary>
/// Enforces the last-administrator invariant (FR-015): a tenant must always retain at least one
/// active <see cref="Role.Administrator"/> membership, so removing or demoting the sole
/// administrator must be refused.
/// </summary>
/// <remarks>
/// This is a minimal stub (T067) — every method throws <see cref="NotImplementedException"/>.
/// It exists only so the solution builds and <c>LastAdministratorTests</c> fails at runtime
/// rather than at compile time. The real invariant-enforcing logic is T074's job, implemented
/// against the test file as its spec.
/// </remarks>
public static class TenantAdministration
{
    /// <summary>
    /// Verifies that removing <paramref name="membershipToRemove"/> from
    /// <paramref name="activeMemberships"/> would not leave the tenant with zero active
    /// administrators.
    /// </summary>
    /// <param name="activeMemberships">The tenant's current active memberships.</param>
    /// <param name="membershipToRemove">The membership being removed.</param>
    /// <exception cref="DomainException">Thrown if <paramref name="membershipToRemove"/> is the
    /// tenant's sole active administrator.</exception>
    public static void EnsureRemovalAllowed(
        IEnumerable<Membership> activeMemberships,
        Membership membershipToRemove)
    {
        throw new NotImplementedException();
    }

    /// <summary>
    /// Verifies that changing <paramref name="membershipToChange"/>'s role to
    /// <paramref name="newRole"/> would not leave the tenant with zero active administrators.
    /// </summary>
    /// <param name="activeMemberships">The tenant's current active memberships.</param>
    /// <param name="membershipToChange">The membership whose role is being changed.</param>
    /// <param name="newRole">The role being assigned to <paramref name="membershipToChange"/>.</param>
    /// <exception cref="DomainException">Thrown if <paramref name="membershipToChange"/> is the
    /// tenant's sole active administrator and <paramref name="newRole"/> is not
    /// <see cref="Role.Administrator"/>.</exception>
    public static void EnsureRoleChangeAllowed(
        IEnumerable<Membership> activeMemberships,
        Membership membershipToChange,
        Role newRole)
    {
        throw new NotImplementedException();
    }
}
