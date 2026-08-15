using Tenancy.Domain.Abstractions;

namespace Tenancy.Application.Abstractions;

/// <summary>
/// Provides access to the resolved tenant context for the current request,
/// including the tenant ID and the caller's role within that tenant.
/// </summary>
/// <remarks>
/// This abstraction is populated by middleware (or similar request-scoped infrastructure)
/// after tenant membership has been validated. Both <see cref="TenantId"/> and <see cref="Role"/>
/// properties must throw an exception (e.g., <see cref="InvalidOperationException"/> or
/// <see cref="DomainException"/>) if accessed before the tenant context has been resolved
/// for the current request. This fail-closed behavior prevents silent security failures where
/// unresolved/default values could be misused downstream as real filter values.
/// Implementations must ensure that accessing these properties before resolution always throws,
/// never returning a default value (such as empty GUID or default enum member).
/// </remarks>
public interface ITenantContext
{
    /// <summary>
    /// Gets the strongly-typed identifier for the current tenant.
    /// </summary>
    /// <remarks>
    /// Throws if the tenant context has not been resolved for the current request.
    /// </remarks>
    /// <exception cref="InvalidOperationException">
    /// Thrown if the tenant context has not been resolved.
    /// </exception>
    TenantId TenantId { get; }

    /// <summary>
    /// Gets the role of the caller within the current tenant.
    /// </summary>
    /// <remarks>
    /// Throws if the tenant context has not been resolved for the current request.
    /// </remarks>
    /// <exception cref="InvalidOperationException">
    /// Thrown if the tenant context has not been resolved.
    /// </exception>
    Role Role { get; }
}
