using Microsoft.Extensions.Logging;
using Tenancy.Application.Abstractions;
using Tenancy.Application.Users;
using Tenancy.Domain.Abstractions;
using Tenancy.Domain.Invitations;
using Tenancy.Domain.Memberships;

namespace Tenancy.Application.Invitations;

/// <summary>
/// Accepts a pending invitation by its raw token (FR-013), for
/// <c>POST /invitations/{token}/accept</c> (T078 wires the endpoint — this is application-layer
/// only). The third ADR-017 exception, alongside <c>CreateTenant</c> (T054) and
/// <see cref="ITenantRepository.GetManyByIdsAsync"/> (T055): the caller has no ambient tenant
/// context yet at entry — they are not a member of anything until acceptance succeeds.
/// </summary>
/// <remarks>
/// <para>
/// <b>Lookup by token hash, across tenants:</b> the caller presents a bare raw token; this use
/// case hashes it and looks the <see cref="Invitation"/> up via
/// <see cref="IInvitationRepository.FindByTokenHashAsync"/>, which deliberately bypasses the
/// tenant-scoping query filter (see that method's remarks for why this specific bypass is safe).
/// </para>
/// <para>
/// <b>Unknown token vs. found-but-not-acceptable, both map to 404, distinguished internally:</b>
/// per T065's tests and contracts/openapi.yaml, an unrecognised token and a
/// found/expired/already-accepted/revoked token both surface as <c>404 Not Found</c> at the API
/// layer — but this use case distinguishes them via
/// <see cref="AcceptInvitationResultKind.NotFound"/> (no matching row at all) vs.
/// <see cref="AcceptInvitationResultKind.NotAcceptable"/> (a row exists but
/// <see cref="Invitation.Accept"/> refused it — not <see cref="InvitationStatus.Pending"/>, or
/// past <see cref="Invitation.ExpiresAtUtc"/>), so the API layer (T078) can map both to the same
/// 404 without needing to inspect a <see cref="DomainException"/> message.
/// </para>
/// <para>
/// <b>Wrong identity maps to 403, distinct from the 404 family:</b> per FR-013 and
/// contracts/openapi.yaml, if the authenticated caller's (JIT-provisioned via
/// <see cref="EnsureUserProvisioned"/>, T036 — same as <c>POST /tenants</c>'s T058 wiring)
/// <c>User.Email</c> does not match <see cref="Invitation.Email"/>, this is reported as
/// <see cref="AcceptInvitationResultKind.WrongIdentity"/> (403), checked before
/// <see cref="Invitation.Accept"/> is called — a caller who is not the invitee should not be able
/// to consume/expire someone else's invitation by attempting to accept it. Comparing two already
/// <see cref="EmailAddress"/>-normalised (lowercase, per <see cref="EmailAddress"/>'s own
/// constructor) values with <c>==</c> is correct here: <see cref="EmailAddress"/> is a
/// <see langword="readonly record struct"/>, so its generated equality is a value comparison on
/// the already-normalised <see cref="EmailAddress.Value"/> string — no separate
/// case-insensitive comparison is needed.
/// </para>
/// <para>
/// <b>One transaction, two aggregates:</b> once expiry/status (<see cref="Invitation.Accept"/>)
/// and identity both pass, a new <see cref="Membership"/> is created for the caller in the
/// invitation's tenant with the invitation's <see cref="Invitation.Role"/>, and both the
/// <see cref="Invitation"/>'s status change and the new <see cref="Membership"/> are persisted in
/// one <see cref="IInvitationRepository.SaveAcceptedAsync"/> call — mirroring
/// <c>CreateTenant</c>'s (T054) "set <c>CurrentTenantId</c> before the save that includes the new
/// aggregate, one <c>SaveChangesAsync</c> call" precedent for the same "no ambient tenant yet"
/// shape.
/// </para>
/// <para>
/// <b>Logging (FR-025):</b> logs the tenant id, new user id, and granted role — never the raw
/// token or its hash. A token hash is still credential-adjacent (it identifies exactly one
/// invitation/invitee, the same reasoning <c>EnsureUserProvisioned</c>/T059 applied to bearer
/// tokens), so it is deliberately omitted, not merely forgotten.
/// </para>
/// </remarks>
public class AcceptInvitation
{
    private readonly IInvitationRepository _invitationRepository;
    private readonly EnsureUserProvisioned _ensureUserProvisioned;
    private readonly IClock _clock;
    private readonly ILogger<AcceptInvitation> _logger;

    public AcceptInvitation(
        IInvitationRepository invitationRepository,
        EnsureUserProvisioned ensureUserProvisioned,
        IClock clock,
        ILogger<AcceptInvitation> logger)
    {
        _invitationRepository = invitationRepository;
        _ensureUserProvisioned = ensureUserProvisioned;
        _clock = clock;
        _logger = logger;
    }

    /// <summary>
    /// Accepts the invitation identified by <paramref name="rawToken"/> on behalf of the
    /// authenticated caller, JIT-provisioning their <see cref="Domain.Users.User"/> row first if
    /// needed.
    /// </summary>
    /// <param name="rawToken">The raw, base64url-encoded invitation token
    /// (<see cref="InvitationToken.Generate"/>) as presented by the caller. Hashed here before any
    /// lookup or logging — never persisted or logged in raw or hashed form.</param>
    /// <param name="callerEntraTenantId">The authenticated caller's Entra tenant id, for JIT
    /// user provisioning.</param>
    /// <param name="callerEntraObjectId">The authenticated caller's Entra object id, for JIT
    /// user provisioning.</param>
    /// <param name="callerEmail">The authenticated caller's email address, for JIT user
    /// provisioning and the identity-match check against <see cref="Invitation.Email"/>.</param>
    public async Task<AcceptInvitationResult> ExecuteAsync(
        string rawToken,
        Guid callerEntraTenantId,
        Guid callerEntraObjectId,
        EmailAddress callerEmail,
        CancellationToken ct)
    {
        var tokenHashBase64 = Convert.ToBase64String(InvitationToken.Hash(rawToken));

        var invitation = await _invitationRepository.FindByTokenHashAsync(tokenHashBase64, ct);
        if (invitation is null)
        {
            return AcceptInvitationResult.NotFound();
        }

        var caller = await _ensureUserProvisioned.ExecuteAsync(
            callerEntraTenantId, callerEntraObjectId, callerEmail, ct);

        if (caller.Email != invitation.Email)
        {
            return AcceptInvitationResult.WrongIdentity();
        }

        try
        {
            invitation.Accept(_clock);
        }
        catch (DomainException)
        {
            // Found, but not pending or already past expiry — collapses to the same 404 signal
            // as an unknown token per T065's tests; the API layer does not need to distinguish
            // the two.
            return AcceptInvitationResult.NotAcceptable();
        }

        var membership = Membership.Create(invitation.TenantId, caller.Id, invitation.Role);

        await _invitationRepository.SaveAcceptedAsync(invitation, membership, ct);

        _logger.LogInformation(
            "Invitation accepted for tenant {TenantId}, granting user {UserId} role {Role}",
            invitation.TenantId,
            caller.Id,
            invitation.Role);

        return AcceptInvitationResult.Success(invitation.TenantId, membership);
    }
}

/// <summary>
/// The outcome of <see cref="AcceptInvitation.ExecuteAsync"/>. See
/// <see cref="AcceptInvitationResultKind"/> for how the API layer (T078) is expected to map each
/// kind to an HTTP status.
/// </summary>
/// <param name="Kind">Which outcome occurred.</param>
/// <param name="TenantId">The tenant the caller just joined. Only set when
/// <paramref name="Kind"/> is <see cref="AcceptInvitationResultKind.Success"/>.</param>
/// <param name="Membership">The newly created membership. Only set when <paramref name="Kind"/>
/// is <see cref="AcceptInvitationResultKind.Success"/>.</param>
public record AcceptInvitationResult(
    AcceptInvitationResultKind Kind,
    TenantId? TenantId,
    Membership? Membership)
{
    public static AcceptInvitationResult Success(TenantId tenantId, Membership membership) =>
        new(AcceptInvitationResultKind.Success, tenantId, membership);

    public static AcceptInvitationResult NotFound() =>
        new(AcceptInvitationResultKind.NotFound, null, null);

    public static AcceptInvitationResult NotAcceptable() =>
        new(AcceptInvitationResultKind.NotAcceptable, null, null);

    public static AcceptInvitationResult WrongIdentity() =>
        new(AcceptInvitationResultKind.WrongIdentity, null, null);
}

/// <summary>
/// The discriminant of <see cref="AcceptInvitationResult"/>. <see cref="NotFound"/> and
/// <see cref="NotAcceptable"/> are deliberately distinct signals despite both mapping to the same
/// <c>404 Not Found</c> at the API layer (T078) — see <see cref="AcceptInvitation"/>'s remarks for
/// why they are not collapsed into one signal here.
/// </summary>
public enum AcceptInvitationResultKind
{
    /// <summary>Accepted: the invitation was valid, pending, unexpired, and matched the caller's
    /// identity. A new <see cref="Membership"/> was created. Maps to a success response.</summary>
    Success,

    /// <summary>No <see cref="Invitation"/> exists with a matching token hash. Maps to
    /// <c>404 Not Found</c>.</summary>
    NotFound,

    /// <summary>An <see cref="Invitation"/> was found, but is not
    /// <see cref="InvitationStatus.Pending"/> (already accepted/revoked) or is past
    /// <see cref="Invitation.ExpiresAtUtc"/>. Maps to <c>404 Not Found</c>, indistinguishable from
    /// <see cref="NotFound"/> at the API layer per T065's tests.</summary>
    NotAcceptable,

    /// <summary>An <see cref="Invitation"/> was found and is still acceptable, but the
    /// authenticated caller's email does not match <see cref="Invitation.Email"/>. Maps to
    /// <c>403 Forbidden</c>.</summary>
    WrongIdentity,
}
