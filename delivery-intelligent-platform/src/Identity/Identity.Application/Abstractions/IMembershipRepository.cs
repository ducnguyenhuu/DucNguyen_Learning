using Identity.Domain.Abstractions;
using Identity.Domain.Memberships;

namespace Identity.Application.Abstractions;

/// <summary>
/// Repository port for <see cref="Domain.Memberships.Membership"/> persistence: the
/// concurrency-guarded writes that enforce the last-administrator invariant (FR-015,
/// <c>OrganizationAdministration</c>) and the first-administrator bootstrap (ADR-025), plus the
/// plain reads that sit alongside them.
/// </summary>
/// <remarks>
/// <see cref="RemoveMembershipAsync"/> and <see cref="TryAddFirstAdministratorAsync"/> are the
/// only operations here whose correctness depends on serializing concurrent callers. The use
/// cases call them directly rather than re-implementing that protection on top of
/// <c>IdentityDbContext</c>, so it lives in exactly one place. Keeping all
/// <see cref="Domain.Memberships.Membership"/> persistence — reads and guarded writes — behind one
/// port avoids a second near-empty interface for a single aggregate.
/// </remarks>
public interface IMembershipRepository
{
    /// <summary>
    /// Returns every <see cref="MembershipStatus.Active"/> membership in the organization, for
    /// <c>GET /members</c> (<c>ListMembers</c>) and the last-administrator check in
    /// <c>ChangeMemberRole</c>.
    /// </summary>
    Task<IReadOnlyList<Membership>> GetActiveMembersAsync(CancellationToken ct);

    /// <summary>
    /// Returns the <see cref="MembershipStatus.Active"/> membership for <paramref name="userId"/>,
    /// or <c>null</c> if that user has no active membership (either never a member, or already
    /// removed).
    /// </summary>
    Task<Membership?> GetActiveMembershipForUserAsync(UserId userId, CancellationToken ct);

    /// <summary>
    /// Removes (soft-deletes, via <see cref="Domain.Memberships.Membership.Remove"/>) the
    /// membership identified by <paramref name="membershipId"/>, guarding the removal against the
    /// last-administrator invariant while genuinely concurrent removals are in flight.
    /// </summary>
    /// <remarks>
    /// The signature deliberately says nothing about transaction isolation levels or locking —
    /// that is an infrastructure concern. The implementation is responsible for ensuring that,
    /// when two callers race to remove two different administrators leaving exactly one behind,
    /// at most one removal can succeed.
    /// </remarks>
    /// <param name="membershipId">The id of the membership to remove.</param>
    /// <param name="ct">Cancellation token.</param>
    /// <exception cref="DomainException">Thrown if removing this membership would leave the
    /// organization with zero active administrators.</exception>
    Task RemoveMembershipAsync(MembershipId membershipId, CancellationToken ct);

    /// <summary>
    /// Adds <paramref name="administratorMembership"/> and saves it, but only if the organization
    /// has no active membership at all yet. Returns <c>false</c>, without saving anything, if it
    /// already has one.
    /// </summary>
    /// <remarks>
    /// Like <see cref="RemoveMembershipAsync"/>, the implementation must serialize concurrent
    /// callers: two first sign-ins racing to bootstrap must produce exactly one administrator.
    /// </remarks>
    Task<bool> TryAddFirstAdministratorAsync(Membership administratorMembership, CancellationToken ct);

    /// <summary>
    /// Persists changes already applied to <paramref name="membership"/> (e.g.
    /// <see cref="Domain.Memberships.Membership.ChangeRole"/>, <c>ChangeMemberRole</c>). A plain
    /// <c>SaveChangesAsync</c> against the already-tracked entity, with no
    /// <c>RowVersion</c>/<c>If-Match</c> pinning of its own; that belongs at the endpoint layer
    /// (<c>MemberEndpoints.PatchMemberRoleAsync</c>), which pins the tracked entity's original
    /// <c>RowVersion</c> before calling this use case's save path (ADR-020).
    /// </summary>
    /// <param name="membership">The already-tracked, modified membership to save.</param>
    /// <param name="ct">Cancellation token.</param>
    Task SaveAsync(Membership membership, CancellationToken ct);
}
