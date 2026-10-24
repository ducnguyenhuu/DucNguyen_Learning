using System.Diagnostics;
using Microsoft.AspNetCore.Http;
using Microsoft.Extensions.Logging;

namespace Identity.Api.Middleware;

/// <summary>
/// The "attached to every structured log line" half of request tracing. ASP.NET Core's own
/// hosting diagnostics (plus this codebase's OpenTelemetry instrumentation) already give every
/// request a root <see cref="Activity"/> whose <see cref="Activity.TraceId"/> is either adopted
/// from an incoming W3C <c>traceparent</c> header or freshly generated — that covers "every
/// trace span." This middleware is the other half: it pushes that same TraceId into an
/// <see cref="ILogger.BeginScope{TState}"/> for the lifetime of the request, so every log line
/// any code emits while handling it — present and future call sites, not just ones remembering
/// to interpolate a trace ID by hand — carries the same identifier as its corresponding span.
/// </summary>
/// <remarks>
/// <b>Why a scope, not per-call-site interpolation.</b> A scope is pushed once per request and
/// applies to every subsequent <c>ILogger</c> call anywhere downstream in the pipeline,
/// including code that has no idea this middleware exists. Interpolating the trace ID into
/// individual log messages would only cover the specific call sites someone remembered to
/// touch, silently missing every other one (and every one added later) — it does not satisfy
/// "every structured log line."
/// </remarks>
/// <remarks>
/// <b>Why registered as classic middleware, not an <see cref="IEndpointFilter"/>.</b> Unlike
/// <see cref="TenantContextResolutionMiddleware"/>, this applies uniformly to every request
/// regardless of route shape (including endpoints with no <c>{tenantId}</c> segment at all), so
/// there is no per-endpoint opt-in decision to make structural — the opposite of ADR-017's
/// concern. Registering it early in the classic pipeline lets it wrap the exception handler
/// too, so log lines emitted while producing an error response are also correlated.
/// </remarks>
public static class TraceCorrelationLoggingMiddleware
{
    public static IApplicationBuilder UseTraceCorrelationLogging(this IApplicationBuilder app)
    {
        return app.Use(async (context, next) =>
        {
            var logger = context.RequestServices
                .GetRequiredService<ILoggerFactory>()
                .CreateLogger(typeof(TraceCorrelationLoggingMiddleware).FullName!);

            var traceId = Activity.Current?.TraceId.ToHexString();

            using (logger.BeginScope(new Dictionary<string, object?> { ["TraceId"] = traceId }))
            {
                await next(context);
            }
        });
    }
}
