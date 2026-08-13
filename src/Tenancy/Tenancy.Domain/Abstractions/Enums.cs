namespace Tenancy.Domain.Abstractions;

/// <summary>
/// Represents the role of a member in a tenant.
/// </summary>
public enum Role
{
    /// <summary>
    /// An administrator with full control over the tenant and its members.
    /// </summary>
    Administrator,

    /// <summary>
    /// A member with full access to the tenant.
    /// </summary>
    Member,

    /// <summary>
    /// A member with read-only access to the tenant.
    /// </summary>
    Reader,
}

/// <summary>
/// Represents the lifecycle state of a tenant.
/// </summary>
public enum TenantStatus
{
    /// <summary>
    /// The tenant is active and operational.
    /// </summary>
    Active,

    /// <summary>
    /// The tenant has been suspended and is not operational.
    /// </summary>
    Suspended,
}

/// <summary>
/// Represents the lifecycle state of a tenant membership.
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
/// Represents the lifecycle state of a tenant invitation.
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
