using Identity.Application.Abstractions;
using Identity.Domain.Abstractions;

namespace Identity.Infrastructure.Security;

/// <summary>
/// The concrete, request-scoped <see cref="ICallerContext"/> implementation. Populated exactly
/// once per request by <c>MembershipResolutionFilter</c> after an active membership has been
/// proven for the caller. Registered as <b>scoped</b> DI so its lifetime matches the request — a
/// singleton would leak one request's caller into another; a transient would be a different
/// instance than the one the filter populated when a downstream handler resolves it.
/// </summary>
/// <remarks>
/// Before <see cref="Resolve"/> is called, <see cref="UserId"/> and <see cref="Role"/> throw
/// rather than returning a default value. This is deliberate fail-closed behavior: the default
/// <see cref="Domain.Abstractions.Role"/> is <see cref="Domain.Abstractions.Role.Administrator"/>
/// (the enum's first member), so a default read by mistake would silently grant administrator
/// powers — exactly the kind of ordering bug this guard exists to surface.
/// </remarks>
public sealed class HttpContextCallerContext : ICallerContext
{
    private (UserId UserId, Role Role)? _resolved;

    /// <inheritdoc />
    public UserId UserId => Resolved().UserId;

    /// <inheritdoc />
    public Role Role => Resolved().Role;

    /// <summary>
    /// Called exactly once per request by <c>MembershipResolutionFilter</c>, after an active
    /// membership has been found for the caller. Not part of <see cref="ICallerContext"/> itself —
    /// that interface is read-only by design, so only infrastructure holding a concrete reference
    /// to this type (the resolution filter) can populate it. Downstream application code can only
    /// ever read.
    /// </summary>
    /// <param name="userId">The caller's user id.</param>
    /// <param name="role">The caller's role from their active membership.</param>
    /// <exception cref="InvalidOperationException">
    /// Thrown if called more than once for the same request scope — resolution is a one-time
    /// event; a second call would indicate a bug in the resolution filter itself.
    /// </exception>
    public void Resolve(UserId userId, Role role)
    {
        if (_resolved is not null)
        {
            throw new InvalidOperationException(
                "Caller context has already been resolved for this request scope.");
        }

        _resolved = (userId, role);
    }

    private (UserId UserId, Role Role) Resolved()
    {
        return _resolved
            ?? throw new InvalidOperationException(
                "Caller context has not been resolved for this request. This means code ran " +
                "before MembershipResolutionFilter, or on a route that does not use " +
                "RequireMembership() and should not be reading ICallerContext at all.");
    }
}
