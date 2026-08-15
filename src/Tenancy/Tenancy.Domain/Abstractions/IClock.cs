namespace Tenancy.Domain.Abstractions;

/// <summary>
/// Abstraction for system clock to enable testable time-dependent logic.
/// Tests can inject a fake clock with fixed time; production uses SystemClock.
/// </summary>
public interface IClock
{
    /// <summary>
    /// Gets the current date and time in UTC.
    /// </summary>
    DateTimeOffset UtcNow { get; }
}

/// <summary>
/// Production implementation of IClock that returns the actual system time.
/// </summary>
public sealed class SystemClock : IClock
{
    /// <summary>
    /// Gets the current date and time in UTC.
    /// </summary>
    public DateTimeOffset UtcNow => DateTimeOffset.UtcNow;
}
