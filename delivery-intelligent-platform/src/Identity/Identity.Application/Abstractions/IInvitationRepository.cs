using Identity.Domain.Abstractions;
using Identity.Domain.Invitations;
using Identity.Domain.Memberships;

namespace Identity.Application.Abstractions;

/// <summary>
/// Repository port for <see cref="Invitation"/> persistence and the membership/pending-invitation
/// existence checks the invitation lifecycle needs.
/// </summary>
/// <remarks>
/// <para>
/// <b>One broader port, named for the aggregate rather than a single use case:</b> inviting,
/// accepting (by token hash), revoking (by id) and listing are all single-aggregate reads and
/// writes against the same <c>Invitation</c> table, so they share one port rather than one per
/// use case.
/// </para>
/// <para>
/// <b>Why <see cref="IsActiveMemberAsync"/> lives here, not on <see cref="IMembershipRepository"/>:</b>
/// it exists purely to answer <c>InviteMember</c>'s "is this email already a member" 409 check.
/// Membership lookups elsewhere are by <c>UserId</c>, so "look up a membership by email" is an
/// invitation-flow check, not a general membership-repository operation.
/// </para>
/// </remarks>
public interface IInvitationRepository
{
    /// <summary>
    /// Returns <see langword="true"/> if <paramref name="email"/> already belongs to a user with
    /// an <c>MembershipStatus.Active</c> membership — the "already an active member" 409 check.
    /// </summary>
    Task<bool> IsActiveMemberAsync(EmailAddress email, CancellationToken ct);

    /// <summary>
    /// Returns <see langword="true"/> if <paramref name="email"/> already has an
    /// <see cref="InvitationStatus.Pending"/> invitation — the "already has a pending invitation"
    /// 409 check. This is an application-level pre-check only; the authoritative backstop under a
    /// race is the database's own <c>UNIQUE (Email) WHERE Status = 'Pending'</c> constraint (see
    /// <see cref="AddAsync"/>'s remarks).
    /// </summary>
    Task<bool> HasPendingInvitationAsync(EmailAddress email, CancellationToken ct);

    /// <summary>
    /// Adds a new <see cref="Invitation"/> and persists it immediately (implementations are
    /// expected to call <c>SaveChangesAsync</c>, not merely stage the addition).
    /// </summary>
    /// <exception cref="Identity.Application.Abstractions.ConcurrencyConflictException">
    /// Thrown if this insert loses a race against a near-simultaneous invitation to the same
    /// email with <c>Status = Pending</c> — the database's unique constraint is the actual
    /// correctness backstop for the "already has a pending invitation" invariant under concurrent
    /// invites, translated by the implementation into this Application-owned type. Callers
    /// (<c>InviteMember</c>) are expected to catch this and translate it into the same conflict
    /// signal as the pre-check, following <c>IdempotencyFilter</c>/<c>EnsureUserProvisioned</c>'s
    /// established insert-and-catch-duplicate pattern rather than relying solely on the
    /// check-then-insert pre-check above, which alone would leave a TOCTOU race window.
    /// </exception>
    Task AddAsync(Invitation invitation, CancellationToken ct);

    /// <summary>
    /// Finds the <see cref="Invitation"/> whose <see cref="Invitation.TokenHash"/> equals
    /// <paramref name="tokenHashBase64"/>, or <see langword="null"/> if none exists — the lookup
    /// <c>AcceptInvitation</c> needs when a bare token arrives from a caller who is not yet a
    /// member.
    /// </summary>
    Task<Invitation?> FindByTokenHashAsync(string tokenHashBase64, CancellationToken ct);

    /// <summary>
    /// Persists the given, already-<see cref="Invitation.Accept"/>ed <paramref name="invitation"/>
    /// together with the new <paramref name="membership"/> created for the accepting user, in a
    /// single <c>SaveChangesAsync</c> call, so the two aggregates change in one transaction.
    /// </summary>
    Task SaveAcceptedAsync(Invitation invitation, Membership membership, CancellationToken ct);

    /// <summary>
    /// Returns every <see cref="InvitationStatus.Pending"/>-stored <see cref="Invitation"/>, for
    /// <c>GET /invitations</c>.
    /// </summary>
    /// <remarks>
    /// Filters to <c>Status == InvitationStatus.Pending</c> only — per the contract's "List
    /// pending invitations" summary (FR-014), <c>Accepted</c>/<c>Revoked</c> rows are not
    /// returned. Note that some rows returned here may already be expired by wall-clock time even
    /// though their stored <see cref="Invitation.Status"/> is still <c>Pending</c> — expiry is
    /// derived, not swept (data-model.md) — so <c>ListInvitations</c> recomputes the effective
    /// status against <see cref="IClock"/> before returning, mirroring
    /// <see cref="Invitation.Accept"/>'s own lazy-expiry-check pattern.
    /// </remarks>
    Task<IReadOnlyList<Invitation>> GetAllPendingAsync(CancellationToken ct);

    /// <summary>
    /// Finds the <see cref="Invitation"/> with the given <paramref name="id"/>, or
    /// <see langword="null"/> if none exists. For <c>DELETE /invitations/{invitationId}</c>.
    /// </summary>
    Task<Invitation?> GetByIdAsync(InvitationId id, CancellationToken ct);

    /// <summary>
    /// Persists an already-mutated, single <paramref name="invitation"/> (e.g. after
    /// <see cref="Invitation.Revoke"/>). Unlike <see cref="SaveAcceptedAsync"/>, this only ever
    /// touches the one <see cref="Invitation"/> aggregate — no second aggregate is involved, so no
    /// atomicity concern beyond EF Core's own single-<c>SaveChangesAsync</c> call.
    /// </summary>
    Task SaveAsync(Invitation invitation, CancellationToken ct);
}
