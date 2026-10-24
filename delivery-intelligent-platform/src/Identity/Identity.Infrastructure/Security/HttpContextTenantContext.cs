using Identity.Application.Abstractions;
using Identity.Domain.Abstractions;

namespace Identity.Infrastructure.Security;

/// <summary>
/// The concrete, request-scoped <see cref="ITenantContext"/> implementation. Populated exactly
/// once per request by <c>TenantContextResolutionMiddleware</c> (ADR-017's single resolution
/// seam) after an active membership has been proven for the caller against the candidate
/// tenant named in the route. Registered as <b>scoped</b> DI so its lifetime matches the request
/// (and, critically, matches <c>IdentityDbContext</c>'s scoped lifetime) — a singleton would leak
/// one request's tenant into another; a transient would be a different instance than the one the
/// middleware populated when a downstream handler resolves it.
/// </summary>
/// <remarks>
/// Before <see cref="Resolve"/> is called, <see cref="TenantId"/> and <see cref="Role"/> throw
/// rather than returning a default value. This is deliberate fail-closed behavior: a default
/// <see cref="Domain.Abstractions.TenantId"/> (an all-zero GUID) used as a filter value by
/// mistake would silently scope a query to a tenant that (almost certainly) does not exist,
/// rather than loudly failing — masking exactly the kind of resolution-order bug ADR-017 exists
/// to prevent.
/// </remarks>
public sealed class HttpContextTenantContext : ITenantContext
{
    private (TenantId TenantId, Role Role)? _resolved;

    /// <inheritdoc />
    public TenantId TenantId => Resolved().TenantId;

    /// <inheritdoc />
    public Role Role => Resolved().Role;

    /// <summary>
    /// Called exactly once per request by the ADR-017 resolution seam, after an active
    /// membership has been found for the caller in the candidate tenant. Not part of
    /// <see cref="ITenantContext"/> itself — that interface is read-only by design, so only
    /// infrastructure holding a concrete reference to this type (the resolution seam) can
    /// populate it. Downstream application/domain code can only ever read.
    /// </summary>
    /// <param name="tenantId">The tenant proven, via an active membership, to be the caller's.</param>
    /// <param name="role">The caller's role within that membership.</param>
    /// <exception cref="InvalidOperationException">
    /// Thrown if called more than once for the same request scope — resolution is a one-time
    /// event; a second call would indicate a bug in the resolution seam itself.
    /// </exception>
    public void Resolve(TenantId tenantId, Role role)
    {
        if (_resolved is not null)
        {
            throw new InvalidOperationException(
                "Tenant context has already been resolved for this request scope.");
        }

        _resolved = (tenantId, role);
    }

    private (TenantId TenantId, Role Role) Resolved()
    {
        return _resolved
            ?? throw new InvalidOperationException(
                "Tenant context has not been resolved for this request. This means code " +
                "ran before TenantContextResolutionMiddleware, or on a route that is one of " +
                "ADR-017's enumerated exceptions and should not be reading ITenantContext at all.");
    }
}
