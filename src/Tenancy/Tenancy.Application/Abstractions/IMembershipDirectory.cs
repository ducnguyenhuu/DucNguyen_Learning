using Tenancy.Domain.Abstractions;
using Tenancy.Domain.Memberships;

namespace Tenancy.Application.Abstractions;

/// <summary>
/// Port for the single sanctioned cross-tenant read in the codebase: listing a user's own
/// active memberships across every tenant they belong to, for <c>GET /tenants</c> (ADR-017).
/// </summary>
/// <remarks>
/// This is not a general-purpose membership query surface. The only implementation
/// (<c>MembershipDirectory</c>, T037) bypasses the tenant-scoping global query filter by name,
/// and only because every result is also filtered to the caller's own <see cref="UserId"/> in
/// the same query. See <see cref="GetMembershipsForUserAsync"/> for the structural constraint.
/// </remarks>
public interface IMembershipDirectory
{
    /// <summary>
    /// Returns all <see cref="MembershipStatus.Active"/> memberships belonging to
    /// <paramref name="userId"/>, across all tenants. The caller's <paramref name="userId"/> is
    /// a required parameter — deliberately, so there is no way to invoke this port without
    /// scoping the result to a specific caller; there is no "list every membership" overload.
    /// </summary>
    Task<IReadOnlyList<Membership>> GetMembershipsForUserAsync(UserId userId, CancellationToken ct);
}
