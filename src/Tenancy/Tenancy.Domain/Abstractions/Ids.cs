namespace Tenancy.Domain.Abstractions;

/// <summary>
/// Strongly-typed identifier for a tenant.
/// Uses Version 7 GUIDs (time-ordered) to avoid clustered index fragmentation.
/// </summary>
public readonly record struct TenantId(Guid Value)
{
    /// <summary>
    /// Creates a new tenant ID using a Version 7 GUID.
    /// </summary>
    public static TenantId New() => new(Guid.CreateVersion7());
}

/// <summary>
/// Strongly-typed identifier for a user.
/// Uses Version 7 GUIDs (time-ordered) to avoid clustered index fragmentation.
/// </summary>
public readonly record struct UserId(Guid Value)
{
    /// <summary>
    /// Creates a new user ID using a Version 7 GUID.
    /// </summary>
    public static UserId New() => new(Guid.CreateVersion7());
}

/// <summary>
/// Strongly-typed identifier for a tenant membership.
/// Uses Version 7 GUIDs (time-ordered) to avoid clustered index fragmentation.
/// </summary>
public readonly record struct MembershipId(Guid Value)
{
    /// <summary>
    /// Creates a new membership ID using a Version 7 GUID.
    /// </summary>
    public static MembershipId New() => new(Guid.CreateVersion7());
}

/// <summary>
/// Strongly-typed identifier for a tenant invitation.
/// Uses Version 7 GUIDs (time-ordered) to avoid clustered index fragmentation.
/// </summary>
public readonly record struct InvitationId(Guid Value)
{
    /// <summary>
    /// Creates a new invitation ID using a Version 7 GUID.
    /// </summary>
    public static InvitationId New() => new(Guid.CreateVersion7());
}
