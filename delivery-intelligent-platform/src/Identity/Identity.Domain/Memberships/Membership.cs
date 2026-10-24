using Identity.Domain.Abstractions;

namespace Identity.Domain.Memberships;

/// <summary>
/// Grants a <c>User</c> a <see cref="Role"/> in the organization. A user has at most one active
/// membership. Never hard-deleted — a
/// membership that loses access is soft-removed via <see cref="Status"/> so FR-025 can later
/// report who lost access and when.
/// </summary>
public class Membership
{
    private Membership(
        MembershipId id,
        UserId userId,
        Role role,
        MembershipStatus status,
        DateTimeOffset? removedAtUtc)
    {
        Id = id;
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
    /// The ID of the user this membership belongs to.
    /// </summary>
    public UserId UserId { get; }

    /// <summary>
    /// The role granted to the user within the organization.
    /// </summary>
    public Role Role { get; private set; }

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
    /// Concurrency token maintained by the database (SQL Server <c>rowversion</c>). Never set by
    /// application code — EF Core populates it on read/write.
    /// </summary>
    public byte[] RowVersion { get; private set; } = [];

    /// <summary>
    /// Creates a new, active membership granting the given user the given role.
    /// </summary>
    /// <param name="userId">The ID of the user being granted access.</param>
    /// <param name="role">The role granted to the user.</param>
    public static Membership Create(UserId userId, Role role)
    {
        return new Membership(
            MembershipId.New(),
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

    /// <summary>
    /// Changes the role granted by this membership to <paramref name="newRole"/>.
    /// </summary>
    /// <remarks>
    /// Unlike <see cref="Accept"/>/<see cref="Revoke"/>'s status-transition guards, this method
    /// does not itself throw <see cref="DomainException"/> for the last-administrator invariant
    /// (FR-015) — that check depends on the organization's full set of active memberships, which this
    /// entity does not have access to, so it is enforced upstream by
    /// <see cref="OrganizationAdministration.EnsureRoleChangeAllowed"/> before
    /// this method is called (T086's <c>ChangeMemberRole</c> use case). This method itself is a
    /// plain setter-with-validation: no role transition is otherwise invalid for a
    /// <see cref="Membership"/>.
    /// </remarks>
    /// <param name="newRole">The role to grant.</param>
    public void ChangeRole(Role newRole)
    {
        Role = newRole;
    }
}
