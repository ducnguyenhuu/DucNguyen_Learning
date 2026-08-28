using Microsoft.Extensions.Logging;
using Tenancy.Application.Abstractions;
using Tenancy.Domain.Abstractions;
using Tenancy.Domain.Auditing;
using Tenancy.Domain.Invitations;

namespace Tenancy.Application.Invitations;

/// <summary>
/// Revokes a pending invitation by id, in the current tenant (FR-014), for
/// <c>DELETE /tenants/{tenantId}/invitations/{invitationId}</c> (the endpoint wiring is
/// application-layer only, not part of this use case). Administrator-only per the contract; that authorization check is not
/// this use case's concern (same division of responsibility as <c>RenameTenant</c>'s remarks).
/// </summary>
/// <remarks>
/// <para>
/// <b>404 vs. 409, per contracts/openapi.yaml:</b> an invitation id that doesn't resolve to a row
/// in the current tenant (either it doesn't exist at all, or it belongs to a different tenant —
/// both indistinguishable, per
/// <see cref="IInvitationRepository.GetByIdForCurrentTenantAsync"/>'s remarks) maps to
/// <see cref="RevokeInvitationResultKind.NotFound"/> (404). A row that exists but is no longer
/// <see cref="InvitationStatus.Pending"/> (already accepted or revoked) maps to
/// <see cref="RevokeInvitationResultKind.Conflict"/> (409 — "Already accepted, so no longer
/// revocable."), signalled by <see cref="Invitation.Revoke"/> throwing <see cref="DomainException"/>.
/// Unlike <see cref="AcceptInvitation"/>'s NotFound/NotAcceptable-both-404 collapse (which exists
/// specifically to avoid leaking token validity to an unauthenticated caller), this is an
/// authenticated, already-tenant-scoped Administrator operating on a known id, and the contract
/// gives the two outcomes genuinely different status codes — no reason to collapse them here.
/// </para>
/// <para>
/// <b>Expired-but-stored-pending invitations are still revocable:</b> this use case does not
/// apply <c>ListInvitations</c>'s lazy-expiry recomputation before calling
/// <see cref="Invitation.Revoke"/> — <see cref="Invitation.Revoke"/> only checks
/// <see cref="Invitation.Status"/>, not <see cref="Invitation.ExpiresAtUtc"/>, so a row that is
/// effectively expired but still stored as <see cref="InvitationStatus.Pending"/> succeeds here,
/// transitioning to <see cref="InvitationStatus.Revoked"/>. This is harmless either way (an
/// expired invitation can never be accepted regardless of whether it is also marked Revoked), and
/// keeping <see cref="Invitation.Revoke"/> as the single source of truth for this check avoids
/// duplicating <see cref="ListInvitations"/>'s clock logic here.
/// </para>
/// <para>
/// <b>Logging (FR-025):</b> logs the tenant id, invitation id, invited email, and the acting
/// (revoking) user id — never the token or its hash, same reasoning as <c>InviteMember</c>/
/// <c>AcceptInvitation</c>.
/// </para>
/// </remarks>
public class RevokeInvitation
{
    private readonly IInvitationRepository _invitationRepository;
    private readonly ITenantContext _tenantContext;
    private readonly IAuditWriter _auditWriter;
    private readonly IClock _clock;
    private readonly ILogger<RevokeInvitation> _logger;

    public RevokeInvitation(
        IInvitationRepository invitationRepository,
        ITenantContext tenantContext,
        IAuditWriter auditWriter,
        IClock clock,
        ILogger<RevokeInvitation> logger)
    {
        _invitationRepository = invitationRepository;
        _tenantContext = tenantContext;
        _auditWriter = auditWriter;
        _clock = clock;
        _logger = logger;
    }

    /// <summary>
    /// Revokes the invitation identified by <paramref name="invitationId"/> in the current
    /// tenant, on behalf of <paramref name="revokedByUserId"/>.
    /// </summary>
    public async Task<RevokeInvitationResult> ExecuteAsync(
        InvitationId invitationId, UserId revokedByUserId, CancellationToken ct)
    {
        var invitation = await _invitationRepository.GetByIdForCurrentTenantAsync(invitationId, ct);
        if (invitation is null)
        {
            return RevokeInvitationResult.NotFound();
        }

        try
        {
            invitation.Revoke();
        }
        catch (DomainException)
        {
            return RevokeInvitationResult.Conflict();
        }

        var auditEntry = AuditEntry.Create(
            _tenantContext.TenantId,
            revokedByUserId,
            "invitation.revoked",
            "Invitation",
            invitation.Id.Value.ToString(),
            _clock);

        // Staged into the same TenancyDbContext instance SaveAsync uses — only staged, not
        // saved, here. SaveAsync's own SaveChangesAsync below flushes the revoked status and
        // this staged entry together, atomically.
        await _auditWriter.RecordAsync(auditEntry, ct);
        await _invitationRepository.SaveAsync(invitation, ct);

        _logger.LogInformation(
            "Invitation {InvitationId} for {Email} revoked in tenant {TenantId} by user {RevokedByUserId}",
            invitation.Id,
            invitation.Email,
            _tenantContext.TenantId,
            revokedByUserId);

        return RevokeInvitationResult.Success();
    }
}

/// <summary>
/// The outcome of <see cref="RevokeInvitation.ExecuteAsync"/>. See
/// <see cref="RevokeInvitationResultKind"/> for how the API layer is expected to map each
/// kind to an HTTP status.
/// </summary>
public record RevokeInvitationResult(RevokeInvitationResultKind Kind)
{
    public static RevokeInvitationResult Success() => new(RevokeInvitationResultKind.Success);

    public static RevokeInvitationResult NotFound() => new(RevokeInvitationResultKind.NotFound);

    public static RevokeInvitationResult Conflict() => new(RevokeInvitationResultKind.Conflict);
}

/// <summary>
/// The discriminant of <see cref="RevokeInvitationResult"/>.
/// </summary>
public enum RevokeInvitationResultKind
{
    /// <summary>The invitation was <see cref="InvitationStatus.Pending"/> and is now
    /// <see cref="InvitationStatus.Revoked"/>. Maps to <c>204 No Content</c>.</summary>
    Success,

    /// <summary>No invitation with the given id exists in the current tenant. Maps to
    /// <c>404 Not Found</c>.</summary>
    NotFound,

    /// <summary>An invitation exists but is not <see cref="InvitationStatus.Pending"/> (already
    /// accepted or revoked). Maps to <c>409 Conflict</c>.</summary>
    Conflict,
}
