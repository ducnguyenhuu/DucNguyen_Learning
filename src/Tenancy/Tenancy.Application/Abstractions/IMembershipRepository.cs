using Tenancy.Domain.Abstractions;
using Tenancy.Domain.Memberships;

namespace Tenancy.Application.Abstractions;

/// <summary>
/// Repository port for <see cref="Domain.Memberships.Membership"/> persistence: both the
/// concurrency-guarded write operation that enforces the last-administrator invariant (FR-015,
/// <c>TenantAdministration</c>) and (T076) the plain reads that sit alongside it.
/// </summary>
/// <remarks>
/// <para>
/// <see cref="RemoveMembershipAsync"/> is a repository-level primitive landed ahead of the use
/// case that will consume it (T075, per its own task brief), mirroring how T070 (token
/// generation) landed before T071 (the use case calling it). T076's <c>RemoveMember</c> use case
/// is expected to call it directly rather than re-implementing this port on top of
/// <c>TenancyDbContext</c>, so the concurrency protection lives in exactly one place.
/// </para>
/// <para>
/// <b>Port-placement decision (T076):</b> <see cref="GetActiveMembersAsync"/> and
/// <see cref="GetActiveMembershipForUserAsync"/> are plain, tenant-scoped reads with no
/// concurrency concerns of their own — they don't need the framing this interface's original doc
/// comment gave it. They were added here anyway, rather than to a new port or to
/// <see cref="IMembershipDirectory"/>, for cohesion: <see cref="IMembershipDirectory"/> is
/// explicitly documented as "the single sanctioned cross-tenant read in the codebase" (a
/// deliberately narrow bypass of the tenant-scoping query filter for the caller's own
/// memberships across tenants) — these two reads are the opposite shape, ordinary
/// current-tenant-scoped reads relying on the ambient <c>TenancyDbContext.CurrentTenantId</c>
/// filter, so folding them into <see cref="IMembershipDirectory"/> would blur that interface's one
/// job. Keeping all <see cref="Domain.Memberships.Membership"/> persistence — reads and the
/// guarded write — behind one port avoids a third near-empty interface for a single aggregate.
/// </para>
/// </remarks>
public interface IMembershipRepository
{
    /// <summary>
    /// Returns every <see cref="MembershipStatus.Active"/> membership in the current tenant
    /// (<c>TenancyDbContext.CurrentTenantId</c>, resolved upstream by tenant-resolution
    /// middleware), for <c>GET /tenants/{tenantId}/members</c> (T076's <c>ListMembers</c>, T079
    /// wires the endpoint).
    /// </summary>
    Task<IReadOnlyList<Membership>> GetActiveMembersAsync(CancellationToken ct);

    /// <summary>
    /// Returns the <see cref="MembershipStatus.Active"/> membership for <paramref name="userId"/>
    /// in the current tenant, or <c>null</c> if that user has no active membership there (either
    /// never a member, or already removed) — for <c>DELETE
    /// /tenants/{tenantId}/members/{userId}</c> (T076's <c>RemoveMember</c>, T079 wires the
    /// endpoint) to resolve the target membership before calling
    /// <see cref="RemoveMembershipAsync"/>.
    /// </summary>
    Task<Membership?> GetActiveMembershipForUserAsync(UserId userId, CancellationToken ct);

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

    /// <summary>
    /// Persists changes already applied to <paramref name="membership"/> (e.g.
    /// <see cref="Domain.Memberships.Membership.ChangeRole"/>, T086's <c>ChangeMemberRole</c> use
    /// case). Mirrors <c>ITenantRepository.SaveAsync</c>'s (T055) minimal shape — a plain
    /// <c>SaveChangesAsync</c> against the already-tracked entity, with no
    /// <c>RowVersion</c>/<c>If-Match</c> pinning of its own; that mechanics belongs at the endpoint
    /// layer (T087), which pins the tracked entity's original <c>RowVersion</c> before calling this
    /// use case's save path, exactly as <c>TenantEndpoints.cs</c>'s
    /// <c>RenameWithOriginalRowVersionAsync</c> already does for <c>Tenant</c>.
    /// </summary>
    /// <param name="membership">The already-tracked, modified membership to save.</param>
    /// <param name="ct">Cancellation token.</param>
    Task SaveAsync(Membership membership, CancellationToken ct);
}
