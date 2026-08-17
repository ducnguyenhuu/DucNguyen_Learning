using Microsoft.Extensions.Logging;
using Tenancy.Application.Abstractions;
using Tenancy.Domain.Abstractions;
using Tenancy.Domain.Invitations;

namespace Tenancy.Application.Invitations;

/// <summary>
/// Invites a prospective member to join the current tenant by email (FR-020), for
/// <c>POST /tenants/{tenantId}/invitations</c> (T078 wires the endpoint — this is
/// application-layer only). The first use case operating on the <see cref="Invitation"/>
/// aggregate.
/// </summary>
/// <remarks>
/// <para>
/// <b>409 conflicts:</b> two invariants are checked, in this order, before anything is persisted
/// — "already an active member" and "already has a pending invitation" — both signalled by
/// throwing <see cref="ConflictException"/> (T071 introduces this <see cref="DomainException"/>
/// subtype specifically so the API layer, T078, can map it to <c>409 Conflict</c> rather than the
/// generic <see cref="DomainException"/>-to-<c>400</c> mapping <c>TenantEndpoints</c> already
/// uses). The "already pending" check is also backed by the database's own
/// <c>UNIQUE (TenantId, Email) WHERE Status = 'Pending'</c> constraint per data-model.md — see
/// <see cref="ExecuteAsync"/>'s handling of <see cref="ConcurrencyConflictException"/> from
/// <see cref="IInvitationRepository.AddAsync"/> for the race backstop, following
/// <c>EnsureUserProvisioned</c> (T036) and <c>IdempotencyFilter</c> (T056)'s established
/// insert-and-catch-duplicate pattern. The "already an active member" check has no equivalent DB
/// race backstop here — a concurrent membership creation is a materially different, much rarer
/// race (it would require a separate concurrent invite-acceptance) not addressed by this task.
/// </para>
/// <para>
/// <b>Token handling:</b> <see cref="InvitationToken.Generate"/> (T070) returns the raw,
/// base64url-encoded token — returned once, in <see cref="InviteMemberResult.RawToken"/>, for the
/// caller (ultimately T078's response body) to hand to the invitee. Only
/// <see cref="InvitationToken.Hash"/>'s <c>byte[32]</c> output is ever persisted, via
/// <see cref="Invitation.TokenHash"/>.
/// </para>
/// <para>
/// <b>byte[]-to-string encoding for <see cref="Invitation.TokenHash"/>:</b> <c>Invitation.Create</c>
/// (an earlier-phase domain type this use case does not own) types <c>tokenHash</c> as
/// <see langword="string"/>, not the <c>byte[32]</c> data-model.md's prose describes. This use
/// case converts <see cref="InvitationToken.Hash"/>'s <c>byte[32]</c> via
/// <see cref="Convert.ToBase64String(byte[])"/> (standard base64, not the base64url
/// <see cref="InvitationToken"/> itself uses for the raw token — this value is never a URL
/// segment, only a persisted, opaque column value, so there is no need to avoid <c>+</c>/<c>/</c>
/// /<c>=</c>). This mirrors <c>RowVersionETag</c>'s (T057) precedent of representing a
/// fixed-length byte array as text for a boundary that expects <see langword="string"/> —
/// <c>RowVersionETag</c> uses base64 for the <c>ETag</c> HTTP-header boundary; this use case uses
/// it for the domain constructor's <see langword="string"/>-typed parameter boundary.
/// </para>
/// <para>
/// <b>7-day expiry (Assumption 6):</b> <c>ExpiresAtUtc = clock.UtcNow + TimeSpan.FromDays(7)</c>,
/// using the injected <see cref="IClock"/> rather than <c>DateTimeOffset.UtcNow</c> directly, so
/// this use case's expiry math is deterministically testable (see <c>InviteMemberTests</c>).
/// </para>
/// <para>
/// <b>Logging and email (FR-025):</b> this logs the invited email address, unlike
/// <c>EnsureUserProvisioned</c>/T059's auth-event logging, which deliberately omits email as
/// "unnecessary personal data" for that scope. An invitation's entire purpose is the invited
/// address — omitting it from FR-025's audit trail here would make the log entry useless for
/// answering "who invited whom" — so it is logged deliberately, not by oversight.
/// </para>
/// </remarks>
public class InviteMember
{
    private readonly IInvitationRepository _invitationRepository;
    private readonly ITenantContext _tenantContext;
    private readonly IClock _clock;
    private readonly IInvitationDeliverySink _deliverySink;
    private readonly ILogger<InviteMember> _logger;

    public InviteMember(
        IInvitationRepository invitationRepository,
        ITenantContext tenantContext,
        IClock clock,
        IInvitationDeliverySink deliverySink,
        ILogger<InviteMember> logger)
    {
        _invitationRepository = invitationRepository;
        _tenantContext = tenantContext;
        _clock = clock;
        _deliverySink = deliverySink;
        _logger = logger;
    }

    /// <summary>
    /// Invites <paramref name="email"/> to join the current tenant with <paramref name="role"/>.
    /// Returns the created, pending <see cref="Invitation"/> together with the raw token — the
    /// caller must surface the raw token to the invitee now; it cannot be recovered later.
    /// </summary>
    /// <param name="email">The prospective member's email address.</param>
    /// <param name="role">The role to grant upon acceptance.</param>
    /// <param name="invitedByUserId">The id of the already-provisioned, already-authorized caller
    /// extending the invitation, for the audit log entry. Authorization (only an Administrator
    /// may invite) is not this use case's concern — same division of responsibility as
    /// <c>RenameTenant</c>'s remarks.</param>
    /// <exception cref="ConflictException">
    /// Thrown if <paramref name="email"/> is already an active member of the current tenant, or
    /// already has a pending invitation to it (checked application-side, and backed by a database
    /// unique-constraint race backstop for the latter).
    /// </exception>
    public async Task<InviteMemberResult> ExecuteAsync(
        EmailAddress email,
        Role role,
        UserId invitedByUserId,
        CancellationToken ct)
    {
        if (await _invitationRepository.IsActiveMemberAsync(email, ct))
        {
            throw new ConflictException($"'{email}' is already an active member of this tenant.");
        }

        if (await _invitationRepository.HasPendingInvitationAsync(email, ct))
        {
            throw new ConflictException($"'{email}' already has a pending invitation to this tenant.");
        }

        var rawToken = InvitationToken.Generate();
        var tokenHash = InvitationToken.Hash(rawToken);
        var tokenHashBase64 = Convert.ToBase64String(tokenHash);

        var expiresAtUtc = _clock.UtcNow + TimeSpan.FromDays(7);
        var invitation = Invitation.Create(_tenantContext.TenantId, email, role, tokenHashBase64, expiresAtUtc);

        try
        {
            await _invitationRepository.AddAsync(invitation, ct);
        }
        catch (ConcurrencyConflictException)
        {
            // Lost the insert race against a near-simultaneous invite to the same address —
            // the database's unique constraint on (TenantId, Email) WHERE Status = 'Pending' is
            // the actual correctness backstop here (see IInvitationRepository.AddAsync's
            // remarks). Translate it into the same 409 signal as the pre-check.
            throw new ConflictException($"'{email}' already has a pending invitation to this tenant.");
        }

        _logger.LogInformation(
            "Invitation {InvitationId} created for {Email} in tenant {TenantId} by user {InvitedByUserId}",
            invitation.Id,
            email,
            invitation.TenantId,
            invitedByUserId);

        // T080/Assumption 8's "delivery" seam — a dev-time stand-in today, a real email send
        // later, both behind the same port. Called only after the invitation is durably
        // persisted above, never before.
        await _deliverySink.DeliverAsync(email, rawToken, ct);

        return new InviteMemberResult(invitation, rawToken);
    }
}

/// <summary>
/// The result of <see cref="InviteMember.ExecuteAsync"/>: the created, pending
/// <see cref="Invitation"/> together with the raw token, returned once. Callers (ultimately
/// T078's endpoint) must surface <see cref="RawToken"/> to the invitee immediately — it is never
/// recoverable again, since only its hash (<see cref="Invitation.TokenHash"/>) is persisted.
/// </summary>
/// <param name="Invitation">The created, pending invitation.</param>
/// <param name="RawToken">The raw, base64url-encoded invitation token (see
/// <see cref="InvitationToken.Generate"/>). Never persisted.</param>
public record InviteMemberResult(Invitation Invitation, string RawToken);
