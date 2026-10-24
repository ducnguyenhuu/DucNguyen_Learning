using System.Diagnostics;
using Microsoft.AspNetCore.Http;
using Microsoft.Extensions.Logging;

namespace Identity.Api.Middleware;

/// <summary>
/// FR-004's user-identity enrichment. User identity (the token's <c>"oid"</c> claim — see
/// <see cref="MembershipResolutionFilter"/>'s own read of it) is known as soon as
/// <c>app.UseAuthentication()</c> has run, for every authenticated request — including the routes
/// that never resolve a membership at all. This middleware is
/// registered immediately after <c>app.UseAuthentication()</c> (before
/// <c>app.UseAuthorization()</c>) so it enriches every authenticated request uniformly,
/// regardless of route shape, the same way <see cref="TraceCorrelationLoggingMiddleware"/> does
/// for TraceId.
/// </summary>
/// <remarks>
/// If the request is unauthenticated (no user, or no <c>"oid"</c> claim), this middleware skips
/// enrichment entirely — no tag, no log scope — and simply calls <c>next(context)</c>. Per FR-004's
/// "when known" wording and the spec's unauthenticated-caller edge case, missing identity at this
/// point is not an error and must never block or fail the request.
/// </remarks>
public static class UserIdentityEnrichmentMiddleware
{
    public static IApplicationBuilder UseUserIdentityEnrichment(this IApplicationBuilder app)
    {
        return app.Use(async (context, next) =>
        {
            var oid = context.User?.FindFirst("oid")?.Value;

            if (string.IsNullOrWhiteSpace(oid))
            {
                await next(context);
                return;
            }

            Activity.Current?.SetTag("user.id", oid);

            var logger = context.RequestServices
                .GetRequiredService<ILoggerFactory>()
                .CreateLogger(typeof(UserIdentityEnrichmentMiddleware).FullName!);

            using (logger.BeginScope(new Dictionary<string, object?> { ["UserId"] = oid }))
            {
                await next(context);
            }
        });
    }
}
