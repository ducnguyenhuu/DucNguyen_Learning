namespace Identity.Domain.Abstractions;

/// <summary>
/// A <see cref="DomainException"/> that signals a conflict with the current state of a resource
/// — the caller's request is well-formed and would otherwise be valid, but cannot proceed
/// because of something that already exists (e.g. a duplicate, an already-active membership, an
/// already-pending invitation). Intended to map to HTTP <c>409 Conflict</c>, distinct from the
/// generic <see cref="DomainException"/>-to-<c>400 Bad Request</c> mapping the endpoints use for
/// invalid-input-shaped invariant violations.
/// </summary>
/// <remarks>
/// This is the first use of a <see cref="DomainException"/> subtype for HTTP-status
/// discrimination in this codebase (T071 — <c>InviteMember</c>). Optimistic-concurrency 409s
/// (e.g. <c>MemberEndpoints.PatchMemberRoleAsync</c>) are signalled by catching a framework type
/// (<c>DbUpdateConcurrencyException</c>) directly, which works for a
/// concurrency race but not for a use case that wants to raise "this specific business conflict"
/// deliberately, before ever touching the database. Endpoint code (T078+) is expected to catch
/// <see cref="ConflictException"/> <b>before</b> the broader <see cref="DomainException"/> catch
/// clause (exception handler ordering matters: the more specific type must come first) and map it
/// to <c>StatusCodes.Status409Conflict</c>, leaving the general <see cref="DomainException"/>
/// catch to keep mapping everything else to <c>400</c>.
/// </remarks>
public class ConflictException : DomainException
{
    /// <summary>
    /// Initializes a new instance of the <see cref="ConflictException"/> class.
    /// </summary>
    public ConflictException()
    {
    }

    /// <summary>
    /// Initializes a new instance of the <see cref="ConflictException"/> class with a specified
    /// error message.
    /// </summary>
    /// <param name="message">The error message that explains the reason for the exception.</param>
    public ConflictException(string message)
        : base(message)
    {
    }

    /// <summary>
    /// Initializes a new instance of the <see cref="ConflictException"/> class with a specified
    /// error message and a reference to the inner exception that is the cause of this exception.
    /// </summary>
    /// <param name="message">The error message that explains the reason for the exception.</param>
    /// <param name="innerException">The exception that is the cause of the current exception.</param>
    public ConflictException(string message, Exception innerException)
        : base(message, innerException)
    {
    }
}
