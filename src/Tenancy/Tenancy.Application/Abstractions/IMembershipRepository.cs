using Tenancy.Domain.Abstractions;

namespace Tenancy.Application.Abstractions;

/// <summary>
/// Repository port for <see cref="Domain.Memberships.Membership"/> write operations that must
/// enforce the last-administrator invariant (FR-015, <c>TenantAdministration</c>) under genuine
/// concurrency, not merely re-check it against a possibly-stale in-memory count.
/// </summary>
/// <remarks>
/// This is a repository-level primitive landed ahead of the use case that will consume it (T075,
/// per its own task brief), mirroring how T070 (token generation) landed before T071 (the use
/// case calling it). T076's <c>RemoveMember</c> use case is expected to call
/// <see cref="RemoveMembershipAsync"/> directly rather than re-implementing this port on top of
/// <c>TenancyDbContext</c>, so the concurrency protection lives in exactly one place.
/// </remarks>
public interface IMembershipRepository
{
    /// <summary>
    /// Removes (soft-deletes, via <see cref="Domain.Memberships.Membership.Remove"/>) the
    /// membership identified by <paramref name="membershipId"/>, guarding the removal against the
    /// last-administrator invariant while genuinely concurrent removals targeting the same
    /// tenant's administrators are in flight.
    /// </summary>
    /// <remarks>
    /// The signature deliberately says nothing about transaction isolation levels or locking —
    /// that is an infrastructure concern. The implementation is responsible for ensuring that,
    /// when two callers race to remove two different administrators of the same tenant leaving
    /// exactly one behind, at most one removal can succeed.
    /// </remarks>
    /// <param name="membershipId">The id of the membership to remove.</param>
    /// <param name="ct">Cancellation token.</param>
    /// <exception cref="DomainException">Thrown if removing this membership would leave the
    /// tenant with zero active administrators.</exception>
    Task RemoveMembershipAsync(MembershipId membershipId, CancellationToken ct);
}
