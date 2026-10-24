using Microsoft.Extensions.Logging;
using Identity.Application.Abstractions;
using Identity.Domain.Abstractions;
using Identity.Domain.Memberships;

namespace Identity.Application.Members;

/// <summary>
/// Lists the organization's active members, for <c>GET /members</c> (T079 wires the endpoint —
/// this is application-layer only). The administrator-only check is the endpoint's
/// (<c>RequireAdministrator()</c>), not this use case's.
/// </summary>
/// <remarks>
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
/// <c>PATCH</c>/<c>DELETE /members/{userId}</c> routes address members by
/// <c>userId</c>, not membership id, so nothing downstream needs it surfaced here.
/// </para>
/// </remarks>
public class ListMembers
{
    private readonly IMembershipRepository _membershipRepository;
    private readonly IUserRepository _userRepository;
    private readonly ILogger<ListMembers> _logger;

    public ListMembers(
        IMembershipRepository membershipRepository,
        IUserRepository userRepository,
        ILogger<ListMembers> logger)
    {
        _membershipRepository = membershipRepository;
        _userRepository = userRepository;
        _logger = logger;
    }

    /// <summary>
    /// Returns every active member of the organization, for the acting
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
            "Listed {Count} active members, requested by user {RequestedByUserId}",
            result.Count,
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
/// <param name="Role">The member's role in the organization.</param>
/// <param name="Status">The membership's lifecycle status (always
/// <see cref="MembershipStatus.Active"/> for rows returned by this use case).</param>
public record ListedMember(UserId UserId, EmailAddress? Email, Role Role, MembershipStatus Status);
