using System.Collections.Concurrent;
using Microsoft.Extensions.Logging;

namespace Tenancy.IntegrationTests.Infrastructure;

/// <summary>
/// A minimal, test-only <see cref="ILoggerProvider"/> that captures every formatted log message
/// produced by the running host into an in-memory, thread-safe collection. Registered by
/// <see cref="ApiFactory.ConfigureWebHost"/> (T053) via
/// <c>builder.ConfigureLogging(logging =&gt; logging.AddProvider(...))</c>, alongside whatever
/// providers the host would otherwise use — this does not replace or suppress them.
/// </summary>
/// <remarks>
/// <para>
/// <b>Why capture the fully-formatted message string, not the structured state.</b> T053's log
/// hygiene test needs to grep captured output for literal substrings (a bearer token, a header
/// value, a fake secret marker) the same way a real log aggregator's full-text search would. The
/// formatted string (<c>formatter(state, exception)</c>, exactly as
/// <see cref="ILogger.Log{TState}"/> hands it to every other provider) is the right representation
/// for that — capturing the raw <c>TState</c> object graph instead would require re-implementing
/// each provider's own formatting logic to answer "does this text ever appear in a rendered log
/// line," which is the actual hygiene question.
/// </para>
/// <para>
/// <b>Why a single, provider-wide capture list instead of one list per <see cref="ILogger"/>
/// category.</b> <see cref="CreateLogger"/> is called once per category name (e.g. once for
/// <c>Microsoft.AspNetCore.Hosting.Diagnostics</c>, once for
/// <c>Microsoft.Identity.Web...</c>, etc.) but a hygiene test cares about "did any log line,
/// anywhere in the request pipeline, leak a secret" — not which specific category logged it.
/// Every <see cref="CapturingLogger"/> instance this provider creates shares this same
/// <see cref="ConcurrentQueue{T}"/> so a test can inspect one flat, chronological view of
/// everything logged, regardless of source.
/// </para>
/// <para>
/// <b>Thread safety.</b> ASP.NET Core logs from multiple threads concurrently (Kestrel's own
/// request-processing threads, background hosted services, etc.), so the backing store is a
/// <see cref="ConcurrentQueue{T}"/> rather than a plain <see cref="List{T}"/> — a plain list
/// would be a silent, intermittent test-flake source under concurrent writes.
/// </para>
/// </remarks>
public sealed class CapturingLoggerProvider : ILoggerProvider
{
    private readonly ConcurrentQueue<string> _messages = new();

    /// <summary>
    /// Every formatted log message captured since this provider was created or last cleared via
    /// <see cref="Clear"/>, in the order logged. A snapshot at the time of the call — later log
    /// activity is not reflected in a previously-returned array.
    /// </summary>
    public string[] Messages => _messages.ToArray();

    /// <summary>
    /// Removes all previously captured messages. <see cref="ApiFactory"/> is shared across an
    /// entire test class via <c>IClassFixture&lt;ApiFactory&gt;</c> (see its type-level remarks),
    /// and this provider — along with its captured messages — lives for that whole shared
    /// instance's lifetime, not per-test. Without an explicit reset, messages from an earlier
    /// test in the same class would still be present when a later test inspects captured logs,
    /// making "no secret appears in the logs for <em>this</em> request" unreliable to assert.
    /// Callers (T053's <c>LogHygieneTests</c>) must call this before the request under test, not
    /// rely on a fresh provider per test.
    /// </summary>
    public void Clear() => _messages.Clear();

    /// <inheritdoc />
    public ILogger CreateLogger(string categoryName) => new CapturingLogger(categoryName, _messages);

    /// <inheritdoc />
    public void Dispose()
    {
    }

    private sealed class CapturingLogger(string categoryName, ConcurrentQueue<string> messages) : ILogger
    {
        public IDisposable? BeginScope<TState>(TState state) where TState : notnull => null;

        public bool IsEnabled(LogLevel logLevel) => true;

        public void Log<TState>(
            LogLevel logLevel,
            EventId eventId,
            TState state,
            Exception? exception,
            Func<TState, Exception?, string> formatter)
        {
            var formatted = formatter(state, exception);
            messages.Enqueue($"[{categoryName}] {formatted}");
        }
    }
}
