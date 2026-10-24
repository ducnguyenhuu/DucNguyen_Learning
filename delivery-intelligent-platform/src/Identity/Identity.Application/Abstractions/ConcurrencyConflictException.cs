namespace Identity.Application.Abstractions;

/// <summary>
/// Signals that a persistence operation lost a race against a concurrent insert with the same
/// unique key — the Application-layer translation of EF Core's <c>DbUpdateException</c>, so that
/// callers needing to detect and recover from this specific condition (the get-or-create race
/// pattern) don't need a dependency on EF Core to catch it.
/// </summary>
/// <remarks>
/// Deliberately a plain <see cref="Exception"/>, not a <c>DomainException</c>: this condition is
/// expected to be caught and resolved internally by a retry (re-reading the row the concurrent
/// writer just inserted) before it ever reaches an endpoint. It is not, by itself, an API-facing
/// error with an HTTP-status mapping the way <c>DomainException</c>/<c>ConflictException</c> are —
/// if a caller lets it propagate, that's a caller-specific decision, not this type's contract.
/// </remarks>
public sealed class ConcurrencyConflictException : Exception
{
    /// <summary>
    /// Initializes a new instance of the <see cref="ConcurrencyConflictException"/> class.
    /// </summary>
    public ConcurrencyConflictException()
    {
    }

    /// <summary>
    /// Initializes a new instance of the <see cref="ConcurrencyConflictException"/> class with a
    /// specified error message.
    /// </summary>
    /// <param name="message">The error message that explains the reason for the exception.</param>
    public ConcurrencyConflictException(string message)
        : base(message)
    {
    }

    /// <summary>
    /// Initializes a new instance of the <see cref="ConcurrencyConflictException"/> class with a
    /// specified error message and a reference to the inner exception that is the cause of this
    /// exception.
    /// </summary>
    /// <param name="message">The error message that explains the reason for the exception.</param>
    /// <param name="innerException">The exception that is the cause of the current exception.</param>
    public ConcurrencyConflictException(string message, Exception innerException)
        : base(message, innerException)
    {
    }
}
