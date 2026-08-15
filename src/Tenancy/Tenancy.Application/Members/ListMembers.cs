using Microsoft.Extensions.Logging;
using Tenancy.Application.Abstractions;
using Tenancy.Domain.Abstractions;
using Tenancy.Domain.Memberships;

namespace Tenancy.Application.Members;

/// <summary>
/// Lists active members of the current tenant, for <c>GET /tenants/{tenantId}/members</c> (T079
/// wires the endpoint — this is application-layer only). "Any active member, any role", same
/// authorization shape as <see cref="Tenants.GetTenant"/> — no extra check here, per that use
/// case's remarks on the division of responsibility.
/// </summary>
/// <remarks>
/// <para>
/// <b>No <c>TenantId</c> parameter:</b> mirrors <see cref="Tenants.GetTenant"/>/
/// <see cref="Tenants.ListTenants"/>'s established shape — the ambient
/// <c>TenancyDbContext.CurrentTenantId</c>, already resolved by upstream tenant-resolution
/// middleware (ADR-017), is the tenant this reads from;
/// <see cref="IMembershipRepository.GetActiveMembersAsync"/> relies on the same global
/// query-filter scoping.
/// </para>
/// <para>
/// <b>Email resolution:</b> <see cref="Domain.Memberships.Membership"/> only carries
/// <see cref="Domain.Memberships.Membership.UserId"/>, not a display email — <c>contracts/openapi.yaml</c>'s
/// <c>Member</c> schema needs one, so this use case does a second, batched lookup via
/// <see cref="IUserRepository.FindByIdsAsync"/> and joins in memory, rather than teaching
/// <see cref="IMembershipRepository"/> about <see cref="Domain.Users.User"/> or adding a
/// cross-aggregate SQL join to either repository port.
/// </para>
/// <para>
/// <b><c>displayName</c> not populated:</b> the <c>Member</c> schema also lists a required
/// <c>displayName</c> field, but <see cref="Domain.Users.User"/> has no such property anywhere in
/// the domain model today (only <see cref="Domain.Users.User.Email"/>) — inventing display-name
/// storage is out of this task's scope (T076 is the list/remove use cases, not a user-profile
/// feature). <see cref="ListedMember"/> therefore omits it; T079 (or a later task) will need to
/// decide how to fill that contract field, e.g. falling back to email.
/// </para>
/// <para>
/// <b>No <c>membershipId</c> field:</b> deliberately excluded — <c>contracts/openapi.yaml</c>'s
/// <c>PATCH</c>/<c>DELETE /tenants/{tenantId}/members/{userId}</c> routes address members by
/// <c>userId</c>, not membership id, so nothing downstream needs it surfaced here.
/// </para>
/// </remarks>
public class ListMembers
{
    private readonly IMembershipRepository _membershipRepository;
    private readonly IUserRepository _userRepository;
    private readonly ITenantContext _tenantContext;
    private readonly ILogger<ListMembers> _logger;

    public ListMembers(
        IMembershipRepository membershipRepository,
        IUserRepository userRepository,
        ITenantContext tenantContext,
        ILogger<ListMembers> logger)
    {
        _membershipRepository = membershipRepository;
        _userRepository = userRepository;
        _tenantContext = tenantContext;
        _logger = logger;
    }

    /// <summary>
    /// Returns every active member of the current tenant, for the acting
    /// <paramref name="requestedByUserId"/> (logged only, not used to filter).
    /// </summary>
    public async Task<IReadOnlyList<ListedMember>> ExecuteAsync(
        UserId requestedByUserId, CancellationToken ct)
    {
        var memberships = await _membershipRepository.GetActiveMembersAsync(ct);

        var userIds = memberships.Select(m => m.UserId).Distinct().ToList();
        var users = await _userRepository.FindByIdsAsync(userIds, ct);
        var usersById = users.ToDictionary(u => u.Id);

        var result = memberships
            .Select(m => new ListedMember(
                m.UserId,
                usersById.TryGetValue(m.UserId, out var user) ? user.Email : null,
                m.Role,
                m.Status))
            .ToList();

        _logger.LogInformation(
            "Listed {Count} active members for tenant {TenantId}, requested by user {RequestedByUserId}",
            result.Count,
            _tenantContext.TenantId,
            requestedByUserId);

        return result;
    }
}

/// <summary>
/// A single member as returned by <see cref="ListMembers"/>. <see cref="Email"/> is <c>null</c>
/// only if the owning <see cref="Domain.Users.User"/> row is unexpectedly missing (should not
/// happen under normal operation — every <see cref="Membership"/> is created for an
/// already-provisioned user).
/// </summary>
/// <param name="UserId">The member's user id.</param>
/// <param name="Email">The member's email address, or <c>null</c> if the owning user could not be
/// resolved.</param>
/// <param name="Role">The member's role in the current tenant.</param>
/// <param name="Status">The membership's lifecycle status (always
/// <see cref="MembershipStatus.Active"/> for rows returned by this use case).</param>
public record ListedMember(UserId UserId, EmailAddress? Email, Role Role, MembershipStatus Status);
