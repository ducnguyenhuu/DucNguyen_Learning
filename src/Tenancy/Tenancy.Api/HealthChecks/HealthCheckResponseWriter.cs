using System.Text.Json;
using Microsoft.Extensions.Diagnostics.HealthChecks;

namespace Tenancy.Api.HealthChecks;

/// <summary>
/// Shapes the JSON body for both <c>/health/live</c> and <c>/health/ready</c> per
/// <c>specs/003-observability/contracts/health-endpoints.md</c>: a top-level <c>status</c>
/// string plus a <c>checks</c> array, each entry carrying <c>name</c>/<c>status</c> and an
/// optional <c>description</c> (omitted when the check reports no description, e.g. the
/// healthy case).
/// </summary>
public static class HealthCheckResponseWriter
{
    private static readonly JsonSerializerOptions SerializerOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
    };

    /// <summary>
    /// Matches <see cref="HealthCheckOptions"/>.ResponseWriter's delegate signature
    /// (<c>Func&lt;HttpContext, HealthReport, Task&gt;</c>).
    /// </summary>
    public static Task WriteResponse(HttpContext context, HealthReport report)
    {
        context.Response.ContentType = "application/json";

        // /health/live runs no checks at all (its MapHealthChecks predicate matches nothing), so
        // report.Entries is empty there; the contract's liveness example omits "checks" entirely
        // rather than showing an empty array, so it's only included when there is at least one
        // check to report (i.e. for /health/ready).
        object payload = report.Entries.Count == 0
            ? new { status = report.Status.ToString() }
            : new
            {
                status = report.Status.ToString(),
                checks = report.Entries.Select(entry => BuildCheck(entry.Key, entry.Value)).ToArray(),
            };

        return context.Response.WriteAsync(
            JsonSerializer.Serialize(payload, SerializerOptions),
            context.RequestAborted);
    }

    /// <summary>
    /// Never surfaces <see cref="HealthReportEntry.Exception"/>'s message: both health routes are
    /// anonymous, and exception text (e.g. a SQL connection failure) routinely carries
    /// server/instance/network detail. Only the curated <see cref="HealthReportEntry.Description"/>
    /// is exposed — the same discipline <c>ProblemDetailsHandler</c> (spec 001) applies to error
    /// responses. An unhealthy check with no description falls back to a fixed generic string
    /// rather than ever reaching for the exception.
    /// </summary>
    private static object BuildCheck(string name, HealthReportEntry entry)
    {
        var description = entry.Status == HealthStatus.Healthy
            ? entry.Description
            : (string.IsNullOrEmpty(entry.Description) ? "Health check failed" : entry.Description);

        return string.IsNullOrEmpty(description)
            ? new { name, status = entry.Status.ToString() }
            : new { name, status = entry.Status.ToString(), description };
    }
}
