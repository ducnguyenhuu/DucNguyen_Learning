using Identity.Domain.Abstractions;

namespace Identity.Domain.Memberships;

/// <summary>
/// Enforces the last-administrator invariant (FR-015): the organization must always retain at
/// least one active <see cref="Role.Administrator"/> membership, so removing or demoting the sole
/// administrator must be refused.
/// </summary>
public static class OrganizationAdministration
{
    /// <summary>
    /// Verifies that removing <paramref name="membershipToRemove"/> from
    /// <paramref name="activeMemberships"/> would not leave the organization with zero active
    /// administrators.
    /// </summary>
    /// <param name="activeMemberships">The organization's current active memberships.</param>
    /// <param name="membershipToRemove">The membership being removed.</param>
    /// <exception cref="DomainException">Thrown if <paramref name="membershipToRemove"/> is the
    /// organization's sole active administrator.</exception>
    public static void EnsureRemovalAllowed(
        IEnumerable<Membership> activeMemberships,
        Membership membershipToRemove)
    {
        var administratorCount = activeMemberships.Count(m => m.Role == Role.Administrator);

        if (membershipToRemove.Role == Role.Administrator && administratorCount == 1)
        {
            throw new DomainException("Cannot remove the sole administrator of the organization.");
        }
    }

    /// <summary>
    /// Verifies that changing <paramref name="membershipToChange"/>'s role to
    /// <paramref name="newRole"/> would not leave the organization with zero active administrators.
    /// </summary>
    /// <param name="activeMemberships">The organization's current active memberships.</param>
    /// <param name="membershipToChange">The membership whose role is being changed.</param>
    /// <param name="newRole">The role being assigned to <paramref name="membershipToChange"/>.</param>
    /// <exception cref="DomainException">Thrown if <paramref name="membershipToChange"/> is the
    /// organization's sole active administrator and <paramref name="newRole"/> is not
    /// <see cref="Role.Administrator"/>.</exception>
    public static void EnsureRoleChangeAllowed(
        IEnumerable<Membership> activeMemberships,
        Membership membershipToChange,
        Role newRole)
    {
        var administratorCount = activeMemberships.Count(m => m.Role == Role.Administrator);

        if (membershipToChange.Role == Role.Administrator &&
            administratorCount == 1 &&
            newRole != Role.Administrator)
        {
            throw new DomainException("Cannot demote the sole administrator of the organization.");
        }
    }
}
