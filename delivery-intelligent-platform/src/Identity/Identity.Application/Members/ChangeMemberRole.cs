using Microsoft.Extensions.Logging;
using Identity.Application.Abstractions;
using Identity.Domain.Abstractions;
using Identity.Domain.Auditing;
using Identity.Domain.Memberships;
using Identity.Domain.Tenants;

namespace Identity.Application.Members;

/// <summary>
/// Changes a member's (by <c>userId</c>) role within the current tenant, for
/// <c>PATCH /tenants/{tenantId}/members/{userId}</c> (the endpoint wiring is application-layer
/// only, not part of this use case). Administrator-only per the contract; that authorization check, and
/// all <c>If-Match</c>/<c>RowVersion</c> precondition handling, are deliberately not this use
/// case's concern — see the remarks below.
/// </summary>
/// <remarks>
/// <para>
/// <b>Scope boundary — no <c>If-Match</c> here:</b> mirroring <c>RenameTenant</c>/
/// <c>TenantEndpoints.cs</c>'s established split and <c>RemoveMember</c>'s own
/// precedent for this exact division, the <c>RowVersion</c>/<c>If-Match</c> precondition
/// disambiguation (412-vs-409) is the endpoint layer's job, not this use case's. This use case is the
/// business-logic layer beneath that: given a target <see cref="UserId"/> and a new
/// <see cref="Role"/>, resolve the target's active membership, resolve all active memberships in
/// the tenant, apply the <see cref="TenantAdministration.EnsureRoleChangeAllowed"/> guard, call
/// <see cref="Membership.ChangeRole"/>, and persist via
/// <see cref="IMembershipRepository.SaveAsync"/>. It deliberately takes no
/// <c>RowVersion</c>/<c>If-Match</c> parameter — the endpoint is expected to have already
/// pinned the tracked entity's original <c>RowVersion</c> before calling
/// <see cref="ExecuteAsync"/>, exactly as <c>TenantEndpoints.cs</c>'s
/// <c>RenameWithOriginalRowVersionAsync</c> does for <c>Tenant</c>.
/// </para>
/// <para>
/// <b>404 vs. 409, mirroring <c>RemoveMember</c>'s precedent:</b> a <c>userId</c> with no
/// active membership in the current tenant maps to
/// <see cref="ChangeMemberRoleResultKind.NotFound"/> (404) — resolved via
/// <see cref="IMembershipRepository.GetActiveMembershipForUserAsync"/>, which is already scoped to
/// the current tenant. A resolved membership that
/// <see cref="TenantAdministration.EnsureRoleChangeAllowed"/> then refuses because it would leave
/// the tenant with zero active administrators throws <see cref="DomainException"/>, caught here
/// and translated to <see cref="ChangeMemberRoleResultKind.Conflict"/> (409) — the same
/// catch-and-translate shape <c>RemoveMember</c> uses for its own repository-thrown
/// <see cref="DomainException"/>, except here the guard is evaluated in this use case rather than
/// inside the repository, since no concurrency-sensitive counting is required (unlike
/// <c>RemoveMembershipAsync</c>'s race-guarded write, this use case's save is a plain
/// <c>SaveChangesAsync</c> whose own optimistic-concurrency check is the endpoint's concern).
/// </para>
/// <para>
/// <b>Logging (FR-025):</b> logs the tenant id, the acting administrator's user id, the target
/// member's user id, and the old and new roles.
/// </para>
/// </remarks>
public class ChangeMemberRole
{
    private readonly IMembershipRepository _membershipRepository;
    private readonly ITenantContext _tenantContext;
    private readonly IAuditWriter _auditWriter;
    private readonly IClock _clock;
    private readonly ILogger<ChangeMemberRole> _logger;

    public ChangeMemberRole(
        IMembershipRepository membershipRepository,
        ITenantContext tenantContext,
        IAuditWriter auditWriter,
        IClock clock,
        ILogger<ChangeMemberRole> logger)
    {
        _membershipRepository = membershipRepository;
        _tenantContext = tenantContext;
        _auditWriter = auditWriter;
        _clock = clock;
        _logger = logger;
    }

    /// <summary>
    /// Changes the active membership for <paramref name="targetUserId"/> in the current tenant to
    /// <paramref name="newRole"/>, on behalf of <paramref name="changedByUserId"/>.
    /// </summary>
    public async Task<ChangeMemberRoleResult> ExecuteAsync(
        UserId targetUserId, Role newRole, UserId changedByUserId, CancellationToken ct)
    {
        var membership = await _membershipRepository.GetActiveMembershipForUserAsync(targetUserId, ct);
        if (membership is null)
        {
            return ChangeMemberRoleResult.NotFound();
        }

        var activeMemberships = await _membershipRepository.GetActiveMembersAsync(ct);

        try
        {
            TenantAdministration.EnsureRoleChangeAllowed(activeMemberships, membership, newRole);
        }
        catch (DomainException)
        {
            return ChangeMemberRoleResult.Conflict();
        }

        var oldRole = membership.Role;

        membership.ChangeRole(newRole);

        var auditEntry = AuditEntry.Create(
            membership.TenantId,
            changedByUserId,
            "membership.role_changed",
            "Membership",
            targetUserId.Value.ToString(),
            _clock);

        // Staged into the same IdentityDbContext instance that IMembershipRepository uses — only
        // staged, not saved, here. SaveAsync below's own SaveChangesAsync flushes both the role
        // change and this staged entry together, atomically. Nothing above this point has staged
        // anything, so a NotFound/Conflict return never leaves a dangling staged entry.
        await _auditWriter.RecordAsync(auditEntry, ct);
        await _membershipRepository.SaveAsync(membership, ct);

        _logger.LogInformation(
            "Member {TargetUserId} role changed from {OldRole} to {NewRole} in tenant {TenantId} by user {ChangedByUserId}",
            targetUserId,
            oldRole,
            newRole,
            _tenantContext.TenantId,
            changedByUserId);

        return ChangeMemberRoleResult.Success(membership);
    }
}

/// <summary>
/// The outcome of <see cref="ChangeMemberRole.ExecuteAsync"/>. See
/// <see cref="ChangeMemberRoleResultKind"/> for how the API layer is expected to map each
/// kind to an HTTP status.
/// </summary>
public record ChangeMemberRoleResult(ChangeMemberRoleResultKind Kind, Membership? Membership = null)
{
    public static ChangeMemberRoleResult Success(Membership membership) =>
        new(ChangeMemberRoleResultKind.Success, membership);

    public static ChangeMemberRoleResult NotFound() => new(ChangeMemberRoleResultKind.NotFound);

    public static ChangeMemberRoleResult Conflict() => new(ChangeMemberRoleResultKind.Conflict);
}

/// <summary>
/// The discriminant of <see cref="ChangeMemberRoleResult"/>.
/// </summary>
public enum ChangeMemberRoleResultKind
{
    /// <summary>The membership was found and its role changed. Maps to <c>200 OK</c>.</summary>
    Success,

    /// <summary>No active membership for the target user exists in the current tenant. Maps to
    /// <c>404 Not Found</c>.</summary>
    NotFound,

    /// <summary>Changing this membership's role would leave the tenant with zero active
    /// administrators. Maps to <c>409 Conflict</c>.</summary>
    Conflict,
}
