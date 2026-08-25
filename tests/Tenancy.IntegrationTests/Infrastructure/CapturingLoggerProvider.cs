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
        // A real provider configured with IncludeScopes = true renders every currently-active
        // BeginScope value into each log line it writes for as long as that scope is in effect.
        // AsyncLocal<T> is what BeginScope itself is built on (see Microsoft.Extensions.Logging's
        // Logger<T>/LoggerExternalScopeProvider), so mirroring that here — rather than returning
        // null and discarding scope state as before — is what makes this test-only provider
        // actually observe request-scoped enrichment (e.g. T021's TraceId scope) the same way a
        // real provider would, instead of being permanently blind to it.
        private static readonly AsyncLocal<ScopeNode?> CurrentScope = new();

        public IDisposable? BeginScope<TState>(TState state) where TState : notnull
        {
            var parent = CurrentScope.Value;
            var node = new ScopeNode(state, parent);
            CurrentScope.Value = node;
            return new ScopePopper(node, parent);
        }

        public bool IsEnabled(LogLevel logLevel) => true;

        public void Log<TState>(
            LogLevel logLevel,
            EventId eventId,
            TState state,
            Exception? exception,
            Func<TState, Exception?, string> formatter)
        {
            var formatted = formatter(state, exception);
            var scopeSuffix = FormatActiveScopes();
            messages.Enqueue($"[{categoryName}] {formatted}{scopeSuffix}");
        }

        private static string FormatActiveScopes()
        {
            var scope = CurrentScope.Value;
            if (scope is null)
            {
                return string.Empty;
            }

            var rendered = new List<string>();
            for (var node = scope; node is not null; node = node.Parent)
            {
                rendered.Add(FormatScopeState(node.State));
            }

            // Outermost scope first, matching the order a real ILogger provider with
            // IncludeScopes = true renders nested BeginScope calls.
            rendered.Reverse();
            return $" [scope: {string.Join(" ", rendered)}]";
        }

        // Mirrors how a real formatted-text provider (e.g. the console logger with
        // IncludeScopes = true) renders a BeginScope(new Dictionary&lt;string, object?&gt; { ... })
        // call: as "Key=Value" pairs, not the object's raw ToString() (which for a
        // Dictionary&lt;,&gt; would just be its type name and would never contain the actual
        // TraceId value this exists to surface).
        private static string FormatScopeState(object? state)
        {
            if (state is System.Collections.IEnumerable enumerable && state is not string)
            {
                var pairs = new List<string>();
                foreach (var entry in enumerable)
                {
                    if (entry is System.Collections.DictionaryEntry dictionaryEntry)
                    {
                        pairs.Add($"{dictionaryEntry.Key}={dictionaryEntry.Value}");
                        continue;
                    }

                    var entryType = entry?.GetType();
                    var keyProperty = entryType?.GetProperty("Key");
                    var valueProperty = entryType?.GetProperty("Value");
                    if (keyProperty is not null && valueProperty is not null)
                    {
                        pairs.Add($"{keyProperty.GetValue(entry)}={valueProperty.GetValue(entry)}");
                        continue;
                    }

                    pairs.Add(entry?.ToString() ?? "null");
                }

                return string.Join(", ", pairs);
            }

            return state?.ToString() ?? "null";
        }

        private sealed class ScopeNode(object state, ScopeNode? parent)
        {
            public object State { get; } = state;

            public ScopeNode? Parent { get; } = parent;
        }

        private sealed class ScopePopper(ScopeNode node, ScopeNode? parent) : IDisposable
        {
            public void Dispose()
            {
                if (CurrentScope.Value == node)
                {
                    CurrentScope.Value = parent;
                }
            }
        }
    }
}
