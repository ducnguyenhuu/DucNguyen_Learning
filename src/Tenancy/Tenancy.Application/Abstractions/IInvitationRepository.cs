using Tenancy.Domain.Abstractions;
using Tenancy.Domain.Invitations;
using Tenancy.Domain.Memberships;

namespace Tenancy.Application.Abstractions;

/// <summary>
/// Repository port for <see cref="Invitation"/> persistence and the membership/pending-invitation
/// existence checks the invitation lifecycle needs, all scoped to the ambient
/// <c>TenancyDbContext.CurrentTenantId</c> (<see cref="Invitation"/> and <c>Membership</c> are
/// both <see cref="ITenantOwned"/>, so the read-side <c>"TenantFilter"</c> query filter already
/// confines every method below to the current tenant with no explicit <c>TenantId</c> parameter
/// needed — mirroring <see cref="ITenantRepository.GetCurrentAsync"/>'s established shape).
/// </summary>
/// <remarks>
/// <para>
/// <b>One broader port, named for the aggregate rather than the single use case (T071's
/// <c>InviteMember</c>):</b> unlike <see cref="ICreateTenantRepository"/> (T054), which stays
/// narrow because it covers exactly one two-aggregate atomic operation, <c>Invitation</c> is
/// about to get several more use cases in this same phase — accepting an invitation (by token
/// hash lookup), revoking one (by id), listing pending invitations — all of which are
/// single-aggregate reads/writes against the same <c>Invitation</c> table, the same shape
/// <see cref="ITenantRepository"/> (T055) already chose to fold into one port rather than one
/// per use case. Naming this <c>IInvitationRepository</c> now, and adding methods as those later
/// use cases land, avoids either speculatively pre-declaring methods nothing calls yet or
/// renaming/re-registering a narrower port partway through the phase.
/// </para>
/// <para>
/// <b>Why <see cref="IsActiveMemberAsync"/> lives here, not on a membership-shaped port:</b> it
/// exists purely to answer <c>InviteMember</c>'s "is this email already a member" 409 check —
/// there is no other current use case that needs "look up a membership by email" as a general
/// operation (membership lookups elsewhere are by <c>UserId</c>, e.g.
/// <c>IMembershipDirectory</c>), so this is invitation-flow-specific, not a general
/// membership-repository operation, and belongs with the other invitation-flow checks here
/// rather than growing a new port of its own.
/// </para>
/// </remarks>
public interface IInvitationRepository
{
    /// <summary>
    /// Returns <see langword="true"/> if <paramref name="email"/> already belongs to an
    /// <c>MembershipStatus.Active</c> membership in the current tenant (i.e. there is already a
    /// <c>User</c> with this email who has an active membership) — the "already an active
    /// member" 409 check.
    /// </summary>
    Task<bool> IsActiveMemberAsync(EmailAddress email, CancellationToken ct);

    /// <summary>
    /// Returns <see langword="true"/> if <paramref name="email"/> already has an
    /// <see cref="InvitationStatus.Pending"/> invitation in the current tenant — the "already has
    /// a pending invitation" 409 check. This is an application-level pre-check only; the
    /// authoritative backstop under a race is the database's own
    /// <c>UNIQUE (TenantId, Email) WHERE Status = 'Pending'</c> constraint (see
    /// <see cref="AddAsync"/>'s remarks).
    /// </summary>
    Task<bool> HasPendingInvitationAsync(EmailAddress email, CancellationToken ct);

    /// <summary>
    /// Adds a new <see cref="Invitation"/> and persists it immediately (implementations are
    /// expected to call <c>SaveChangesAsync</c>, not merely stage the addition).
    /// </summary>
    /// <exception cref="Microsoft.EntityFrameworkCore.DbUpdateException">
    /// Thrown if this insert loses a race against a near-simultaneous invitation to the same
    /// <c>(TenantId, Email)</c> with <c>Status = Pending</c> — the database's unique constraint
    /// is the actual correctness backstop for the "already has a pending invitation" invariant
    /// under concurrent invites, per data-model.md. Callers (<c>InviteMember</c>) are expected to
    /// catch this and translate it into the same conflict signal as the pre-check, following
    /// <c>IdempotencyFilter</c>/<c>EnsureUserProvisioned</c>'s established
    /// insert-and-catch-duplicate pattern (T056/T036) rather than relying solely on the
    /// check-then-insert pre-check above, which alone would leave a TOCTOU race window.
    /// </exception>
    Task AddAsync(Invitation invitation, CancellationToken ct);

    /// <summary>
    /// Finds the <see cref="Invitation"/> whose <see cref="Invitation.TokenHash"/> equals
    /// <paramref name="tokenHashBase64"/>, across every tenant, or <see langword="null"/> if none
    /// exists — the lookup <c>AcceptInvitation</c> (T072) needs when a bare token arrives with no
    /// ambient tenant context yet (the third ADR-017 exception, alongside
    /// <c>CreateTenant</c>/T054 and <see cref="ITenantRepository.GetManyByIdsAsync"/>/T055).
    /// </summary>
    /// <remarks>
    /// Implementations must call <c>IgnoreQueryFilters()</c> to bypass the automatic
    /// <c>"TenantFilter"</c> query filter <see cref="Invitation"/> is normally subject to as an
    /// <c>ITenantOwned</c> entity. This is safe precisely because the lookup predicate is an exact
    /// match on <see cref="Invitation.TokenHash"/> — a SHA-256 hash, effectively unguessable and
    /// unique per invitation — so there is no risk of leaking one tenant's invitations to another;
    /// the caller learns only whether their presented token matches a real invitation, and if so,
    /// which tenant it belongs to (which is exactly what accepting an invitation requires them to
    /// learn). This mirrors <see cref="ITenantRepository.GetManyByIdsAsync"/>'s documented
    /// bypass-by-exact-id-match precedent (T055) — narrow, deliberate, and explained here rather
    /// than left to be rediscovered from a filter-less query.
    /// </remarks>
    Task<Invitation?> FindByTokenHashAsync(string tokenHashBase64, CancellationToken ct);

    /// <summary>
    /// Persists the given, already-<see cref="Invitation.Accept"/>ed <paramref name="invitation"/>
    /// together with the new <paramref name="membership"/> created for the accepting user, in a
    /// single <c>SaveChangesAsync</c> call — mirroring <see cref="ICreateTenantRepository.AddAsync"/>'s
    /// (T054) "one transaction, two aggregates" precedent for the same "no ambient tenant context
    /// yet" situation. Implementations must set <c>TenancyDbContext.CurrentTenantId =
    /// invitation.TenantId</c> before calling <c>SaveChangesAsync</c>, so <c>TenantSaveChangesInterceptor</c>
    /// (T027) stamps the new <paramref name="membership"/> with the correct tenant rather than the
    /// CLR default.
    /// </summary>
    Task SaveAcceptedAsync(Invitation invitation, Membership membership, CancellationToken ct);

    /// <summary>
    /// Returns every <see cref="InvitationStatus.Pending"/>-stored <see cref="Invitation"/> in the
    /// current tenant, for <c>GET /tenants/{tenantId}/invitations</c> (T073). Scoped implicitly by
    /// the ambient <c>"TenantFilter"</c> query filter — no explicit <c>TenantId</c> parameter
    /// needed, mirroring every other method on this port.
    /// </summary>
    /// <remarks>
    /// Filters to <c>Status == InvitationStatus.Pending</c> only — per the contract's "List
    /// pending invitations" summary (FR-014), <c>Accepted</c>/<c>Revoked</c> rows are not
    /// returned. Note that some rows returned here may already be expired by wall-clock time even
    /// though their stored <see cref="Invitation.Status"/> is still <c>Pending</c> — expiry is
    /// derived, not swept (data-model.md) — so <c>ListInvitations</c> (T073) recomputes the
    /// effective status against <see cref="IClock"/> before returning, mirroring
    /// <see cref="Invitation.Accept"/>'s own lazy-expiry-check pattern.
    /// </remarks>
    Task<IReadOnlyList<Invitation>> GetAllForCurrentTenantAsync(CancellationToken ct);

    /// <summary>
    /// Finds the <see cref="Invitation"/> with the given <paramref name="id"/> in the current
    /// tenant, or <see langword="null"/> if none exists (either because no invitation with that id
    /// exists at all, or because one exists but belongs to a different tenant — both
    /// indistinguishable here, same as every other tenant-scoped lookup on this port). For
    /// <c>DELETE /tenants/{tenantId}/invitations/{invitationId}</c> (T073).
    /// </summary>
    Task<Invitation?> GetByIdForCurrentTenantAsync(InvitationId id, CancellationToken ct);

    /// <summary>
    /// Persists an already-mutated, single <paramref name="invitation"/> (e.g. after
    /// <see cref="Invitation.Revoke"/>). Unlike <see cref="SaveAcceptedAsync"/>, this only ever
    /// touches the one <see cref="Invitation"/> aggregate — no second aggregate is involved, so no
    /// atomicity concern beyond EF Core's own single-<c>SaveChangesAsync</c> call.
    /// </summary>
    Task SaveAsync(Invitation invitation, CancellationToken ct);
}
