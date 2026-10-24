using Identity.Domain.Abstractions;

namespace Identity.Application.Abstractions;

/// <summary>
/// The current request's caller, as proven by an active membership: their user id and their
/// role in the organization (ADR-025).
/// </summary>
/// <remarks>
/// This abstraction is populated by request-scoped infrastructure (<c>MembershipResolutionFilter</c>)
/// only after an active membership has been found for the caller. Both <see cref="UserId"/> and
/// <see cref="Role"/> must throw an exception (e.g., <see cref="InvalidOperationException"/>) if
/// accessed before the caller has been resolved for the current request. This fail-closed
/// behavior prevents silent security failures where an unresolved default value (an empty user
/// id, or <see cref="Role.Administrator"/> — the enum's default member) could be misused
/// downstream as a real one. Implementations must ensure that accessing these properties before
/// resolution always throws, never returning a default value.
/// </remarks>
public interface ICallerContext
{
    /// <summary>
    /// Gets the caller's user id.
    /// </summary>
    /// <exception cref="InvalidOperationException">
    /// Thrown if the caller has not been resolved.
    /// </exception>
    UserId UserId { get; }

    /// <summary>
    /// Gets the caller's role in the organization, from their active membership row — never from
    /// a token claim.
    /// </summary>
    /// <exception cref="InvalidOperationException">
    /// Thrown if the caller has not been resolved.
    /// </exception>
    Role Role { get; }
}
