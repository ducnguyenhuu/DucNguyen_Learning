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

    /// <summary>
    /// The fixed sentinel tenant id used where a real tenant does not yet exist (e.g. the
    /// <c>IdempotencyRecord</c> for <c>POST /tenants</c>, which has no tenant context). Not a
    /// real tenant and must never resolve to one — used only so a non-nullable
    /// <see cref="TenantId"/> column can still participate in a composite primary key without
    /// storing <c>NULL</c>.
    /// </summary>
    public static TenantId Empty => new(Guid.Empty);
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
