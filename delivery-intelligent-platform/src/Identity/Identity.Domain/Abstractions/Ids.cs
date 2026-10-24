namespace Identity.Domain.Abstractions;

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
/// Strongly-typed identifier for a membership.
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
/// Strongly-typed identifier for an invitation.
/// Uses Version 7 GUIDs (time-ordered) to avoid clustered index fragmentation.
/// </summary>
public readonly record struct InvitationId(Guid Value)
{
    /// <summary>
    /// Creates a new invitation ID using a Version 7 GUID.
    /// </summary>
    public static InvitationId New() => new(Guid.CreateVersion7());
}

/// <summary>
/// Strongly-typed identifier for an audit entry.
/// Uses Version 7 GUIDs (time-ordered) to avoid clustered index fragmentation.
/// </summary>
public readonly record struct AuditEntryId(Guid Value)
{
    /// <summary>
    /// Creates a new audit entry ID using a Version 7 GUID.
    /// </summary>
    public static AuditEntryId New() => new(Guid.CreateVersion7());
}
