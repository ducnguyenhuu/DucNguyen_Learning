using Microsoft.Extensions.Logging;
using Tenancy.Application.Abstractions;
using Tenancy.Domain.Abstractions;

namespace Tenancy.Application.Members;

/// <summary>
/// Removes a member (by <c>userId</c>) from the current tenant, for
/// <c>DELETE /tenants/{tenantId}/members/{userId}</c> (T079 wires the endpoint — this is
/// application-layer only). Administrator-only per the contract; that authorization check, and
/// all <c>If-Match</c>/<c>RowVersion</c> precondition handling, are deliberately not this use
/// case's concern — see the remarks below.
/// </summary>
/// <remarks>
/// <para>
/// <b>Scope boundary — no <c>If-Match</c> here:</b> <c>contracts/openapi.yaml</c>'s
/// <c>DELETE /tenants/{tenantId}/members/{userId}</c> requires an <c>If-Match</c> header and
/// documents 412/428 (stale/missing precondition) alongside 409 (concurrency race or
/// last-administrator conflict). That HTTP-level precondition disambiguation (mirroring T058's
/// established 412-vs-409 pattern for <c>PATCH /tenants/{tenantId}</c>) is T079's job, at the
/// endpoint layer. This use case is the business-logic layer beneath that: given a target
/// <see cref="UserId"/>, resolve the active membership, remove it race-safely via
/// <see cref="IMembershipRepository.RemoveMembershipAsync"/> (T075 — this use case does not
/// re-implement any of its concurrency protection), and translate the last-administrator
/// <see cref="DomainException"/> into a distinct <see cref="RemoveMemberResultKind.Conflict"/>
/// signal T079 can map to 409. It deliberately takes no <c>RowVersion</c>/<c>If-Match</c>
/// parameter.
/// </para>
/// <para>
/// <b>404 vs. 409, mirroring <c>RevokeInvitation</c>'s (T073) precedent:</b> a <c>userId</c> with
/// no active membership in the current tenant (never a member, already removed, or a member of a
/// different tenant only) maps to <see cref="RemoveMemberResultKind.NotFound"/> (404) — resolved
/// via <see cref="IMembershipRepository.GetActiveMembershipForUserAsync"/>, which is already
/// scoped to the current tenant. A resolved membership that <see cref="IMembershipRepository.RemoveMembershipAsync"/>
/// then refuses to remove because it is the tenant's last administrator throws
/// <see cref="DomainException"/>, caught here and translated to
/// <see cref="RemoveMemberResultKind.Conflict"/> (409) — the same catch-and-translate shape
/// <c>InviteMember</c> (T071) uses for its own <see cref="ConflictException"/> signal, though this
/// use case reuses the plain <see cref="DomainException"/> the repository already throws rather
/// than introducing a second exception type, since the repository is the sole thrower and this is
/// the sole catcher.
/// </para>
/// <para>
/// <b>Logging (FR-025):</b> logs the tenant id, the acting administrator's user id, and the
/// removed member's user id — no email, unlike <c>InviteMember</c>/<c>RevokeInvitation</c>, since
/// (per this task's brief) removal is about an already-known member, not a not-yet-a-member
/// address.
/// </para>
/// </remarks>
public class RemoveMember
{
    private readonly IMembershipRepository _membershipRepository;
    private readonly ITenantContext _tenantContext;
    private readonly ILogger<RemoveMember> _logger;

    public RemoveMember(
        IMembershipRepository membershipRepository,
        ITenantContext tenantContext,
        ILogger<RemoveMember> logger)
    {
        _membershipRepository = membershipRepository;
        _tenantContext = tenantContext;
        _logger = logger;
    }

    /// <summary>
    /// Removes the active membership for <paramref name="targetUserId"/> in the current tenant,
    /// on behalf of <paramref name="removedByUserId"/>.
    /// </summary>
    public async Task<RemoveMemberResult> ExecuteAsync(
        UserId targetUserId, UserId removedByUserId, CancellationToken ct)
    {
        var membership = await _membershipRepository.GetActiveMembershipForUserAsync(targetUserId, ct);
        if (membership is null)
        {
            return RemoveMemberResult.NotFound();
        }

        try
        {
            await _membershipRepository.RemoveMembershipAsync(membership.Id, ct);
        }
        catch (DomainException)
        {
            return RemoveMemberResult.Conflict();
        }

        _logger.LogInformation(
            "Member {RemovedUserId} removed from tenant {TenantId} by user {RemovedByUserId}",
            targetUserId,
            _tenantContext.TenantId,
            removedByUserId);

        return RemoveMemberResult.Success();
    }
}

/// <summary>
/// The outcome of <see cref="RemoveMember.ExecuteAsync"/>. See
/// <see cref="RemoveMemberResultKind"/> for how the API layer (T079) is expected to map each kind
/// to an HTTP status.
/// </summary>
public record RemoveMemberResult(RemoveMemberResultKind Kind)
{
    public static RemoveMemberResult Success() => new(RemoveMemberResultKind.Success);

    public static RemoveMemberResult NotFound() => new(RemoveMemberResultKind.NotFound);

    public static RemoveMemberResult Conflict() => new(RemoveMemberResultKind.Conflict);
}

/// <summary>
/// The discriminant of <see cref="RemoveMemberResult"/>.
/// </summary>
public enum RemoveMemberResultKind
{
    /// <summary>The membership was found and removed. Maps to <c>204 No Content</c>.</summary>
    Success,

    /// <summary>No active membership for the target user exists in the current tenant. Maps to
    /// <c>404 Not Found</c>.</summary>
    NotFound,

    /// <summary>Removing this membership would leave the tenant with zero active administrators.
    /// Maps to <c>409 Conflict</c>.</summary>
    Conflict,
}
