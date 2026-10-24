namespace Identity.Domain.Abstractions;

/// <summary>
/// Represents the role of a member in the organization.
/// </summary>
public enum Role
{
    /// <summary>
    /// An administrator with full control over the organization and its members.
    /// </summary>
    Administrator,

    /// <summary>
    /// A member with full access to the organization.
    /// </summary>
    Member,

    /// <summary>
    /// A member with read-only access to the organization.
    /// </summary>
    Reader,
}

/// <summary>
/// Represents the lifecycle state of a membership.
/// </summary>
public enum MembershipStatus
{
    /// <summary>
    /// The membership is active.
    /// </summary>
    Active,

    /// <summary>
    /// The membership has been soft-removed.
    /// </summary>
    Removed,
}

/// <summary>
/// Represents the lifecycle state of an invitation.
/// </summary>
public enum InvitationStatus
{
    /// <summary>
    /// The invitation is pending acceptance.
    /// </summary>
    Pending,

    /// <summary>
    /// The invitation has been accepted.
    /// </summary>
    Accepted,

    /// <summary>
    /// The invitation has been revoked.
    /// </summary>
    Revoked,

    /// <summary>
    /// The invitation has expired.
    /// </summary>
    Expired,
}
