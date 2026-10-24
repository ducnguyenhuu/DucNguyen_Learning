namespace Identity.Domain.Abstractions;

/// <summary>
/// Marker interface for entities that are owned by a tenant.
/// Entities implementing this interface will have the tenant filter automatically applied in queries.
/// </summary>
public interface ITenantOwned
{
    /// <summary>
    /// Gets the ID of the tenant that owns this entity.
    /// </summary>
    TenantId TenantId { get; }
}
