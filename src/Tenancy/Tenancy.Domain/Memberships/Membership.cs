using Tenancy.Domain.Abstractions;

namespace Tenancy.Domain.Memberships;

/// <summary>
/// Links a <c>User</c> to a <c>Tenant</c> with a <see cref="Role"/>. Never hard-deleted — a
/// membership that loses access is soft-removed via <see cref="Status"/> so FR-025 can later
/// report who lost access and when.
/// </summary>
public class Membership : ITenantOwned
{
    private Membership(
        MembershipId id,
        TenantId tenantId,
        UserId userId,
        Role role,
        MembershipStatus status,
        DateTimeOffset? removedAtUtc)
    {
        Id = id;
        TenantId = tenantId;
        UserId = userId;
        Role = role;
        Status = status;
        RemovedAtUtc = removedAtUtc;
    }

    /// <summary>
    /// The unique identifier of the membership.
    /// </summary>
    public MembershipId Id { get; }

    /// <summary>
    /// The ID of the tenant that this membership grants access to.
    /// </summary>
    public TenantId TenantId { get; }

    /// <summary>
    /// The ID of the user this membership belongs to.
    /// </summary>
    public UserId UserId { get; }

    /// <summary>
    /// The role granted to the user within the tenant.
    /// </summary>
    public Role Role { get; }

    /// <summary>
    /// The lifecycle state of the membership.
    /// </summary>
    public MembershipStatus Status { get; private set; }

    /// <summary>
    /// The timestamp at which the membership was removed, or <c>null</c> while <see cref="Status"/>
    /// is <see cref="MembershipStatus.Active"/>.
    /// </summary>
    public DateTimeOffset? RemovedAtUtc { get; private set; }

    /// <summary>
    /// Creates a new, active membership linking the given user to the given tenant with the given
    /// role.
    /// </summary>
    /// <param name="tenantId">The ID of the tenant granting access.</param>
    /// <param name="userId">The ID of the user being granted access.</param>
    /// <param name="role">The role granted to the user.</param>
    public static Membership Create(TenantId tenantId, UserId userId, Role role)
    {
        return new Membership(
            MembershipId.New(),
            tenantId,
            userId,
            role,
            MembershipStatus.Active,
            removedAtUtc: null);
    }

    /// <summary>
    /// Soft-removes the membership, transitioning <see cref="Status"/> to
    /// <see cref="MembershipStatus.Removed"/> and recording <paramref name="clock"/>'s current
    /// time on <see cref="RemovedAtUtc"/>.
    /// </summary>
    /// <param name="clock">The clock used to read the current time, injected so the entity — not
    /// the caller — is responsible for reading "now".</param>
    /// <exception cref="DomainException">Thrown if the membership is already removed.</exception>
    public void Remove(IClock clock)
    {
        if (Status == MembershipStatus.Removed)
        {
            throw new DomainException("Membership is already removed.");
        }

        Status = MembershipStatus.Removed;
        RemovedAtUtc = clock.UtcNow;
    }
}
