using Tenancy.Domain.Abstractions;
using Tenancy.Domain.Invitations;

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
}
