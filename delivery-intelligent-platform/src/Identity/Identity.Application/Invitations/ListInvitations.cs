using Microsoft.Extensions.Logging;
using Identity.Application.Abstractions;
using Identity.Domain.Abstractions;
using Identity.Domain.Invitations;

namespace Identity.Application.Invitations;

/// <summary>
/// Lists pending invitations (FR-014), for <c>GET /invitations</c> (T078 wires the endpoint — this is
/// application-layer only). Administrator-only per the contract; that authorization check is not
/// this use case's concern (the endpoint applies <c>RequireAdministrator()</c>).
/// </summary>
/// <remarks>
/// <para>
/// <b>Derived expiry, not swept:</b> <see cref="IInvitationRepository.GetAllPendingAsync"/>
/// returns every row whose <i>stored</i> <see cref="Invitation.Status"/> is
/// <see cref="InvitationStatus.Pending"/> — some of those may already be past
/// <see cref="Invitation.ExpiresAtUtc"/> by wall-clock time, since data-model.md rules out a
/// database sweep job for this slice. This use case recomputes the effective status against the
/// injected <see cref="IClock"/> before returning, mirroring <see cref="Invitation.Accept"/>'s own
/// lazy-expiry-check pattern, so the contract's <c>status</c> field (whose enum includes
/// <c>Expired</c>) reflects reality rather than the stale stored value.
/// </para>
/// <para>
/// <b>Why a separate result record, not <see cref="Invitation"/> itself:</b> <see cref="Invitation"/>'s
/// <see cref="Invitation.Status"/> setter is private and only ever transitions via
/// <see cref="Invitation.Accept"/>/<see cref="Invitation.Revoke"/> — deliberately, since writing
/// <see cref="InvitationStatus.Expired"/> to the database is exactly what data-model.md rules out.
/// <see cref="ListedInvitation"/> carries the recomputed, display-only status alongside the rest of
/// the fields T078's response needs, without ever mutating or persisting the entity.
/// </para>
/// </remarks>
public class ListInvitations
{
    private readonly IInvitationRepository _invitationRepository;
    private readonly IClock _clock;
    private readonly ILogger<ListInvitations> _logger;

    public ListInvitations(
        IInvitationRepository invitationRepository,
        IClock clock,
        ILogger<ListInvitations> logger)
    {
        _invitationRepository = invitationRepository;
        _clock = clock;
        _logger = logger;
    }

    /// <summary>
    /// Returns every pending-or-effectively-expired invitation, for the
    /// acting <paramref name="requestedByUserId"/> (logged only, not used to filter).
    /// </summary>
    public async Task<IReadOnlyList<ListedInvitation>> ExecuteAsync(
        UserId requestedByUserId, CancellationToken ct)
    {
        var invitations = await _invitationRepository.GetAllPendingAsync(ct);

        var now = _clock.UtcNow;
        var result = invitations
            .Select(invitation => new ListedInvitation(
                invitation.Id,
                invitation.Email,
                invitation.Role,
                now > invitation.ExpiresAtUtc ? InvitationStatus.Expired : invitation.Status,
                invitation.ExpiresAtUtc))
            .ToList();

        _logger.LogInformation(
            "Listed {Count} pending invitations, requested by user {RequestedByUserId}",
            result.Count,
            requestedByUserId);

        return result;
    }
}

/// <summary>
/// A single invitation as returned by <see cref="ListInvitations"/>, carrying the recomputed,
/// display-only <see cref="Status"/> (see <see cref="ListInvitations"/>'s remarks) rather than
/// <see cref="Invitation.Status"/>'s stored value.
/// </summary>
/// <param name="Id">The invitation's id.</param>
/// <param name="Email">The invitee's email address.</param>
/// <param name="Role">The role to be granted upon acceptance.</param>
/// <param name="Status">The effective status, with <see cref="InvitationStatus.Expired"/>
/// recomputed against the current time rather than trusted from the stored value.</param>
/// <param name="ExpiresAtUtc">The timestamp after which the invitation can no longer be
/// accepted.</param>
public record ListedInvitation(
    InvitationId Id,
    EmailAddress Email,
    Role Role,
    InvitationStatus Status,
    DateTimeOffset ExpiresAtUtc);
