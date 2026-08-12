using Microsoft.AspNetCore.Diagnostics;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;

namespace Tenancy.Api.ErrorHandling;

/// <summary>
/// Global unhandled-exception handler (FR-022). Converts every unhandled exception into a
/// generic RFC 9457 (application/problem+json) response.
///
/// Hard requirement: the response body must never contain <c>exception.Message</c>,
/// <c>exception.ToString()</c>/<c>StackTrace</c>, the exception's type name, or any other
/// internal detail — including anything that could reveal whether a specific resource (in
/// particular, another tenant) exists. Only a static, generic title/detail is ever written.
///
/// This is distinct from T035's tenant-resolution middleware, which writes a bare 404 directly
/// and never reaches this handler (it never throws) — the two are separate, deliberately
/// non-overlapping code paths.
/// </summary>
public class ProblemDetailsHandler : IExceptionHandler
{
    private readonly ILogger<ProblemDetailsHandler> _logger;

    public ProblemDetailsHandler(ILogger<ProblemDetailsHandler> logger)
    {
        _logger = logger;
    }

    public async ValueTask<bool> TryHandleAsync(
        HttpContext httpContext,
        Exception exception,
        CancellationToken cancellationToken)
    {
        // Full exception detail (message, stack trace, type) goes only to structured logs —
        // never to the response body written below.
        _logger.LogError(
            exception,
            "Unhandled exception processing {Method} {Path}",
            httpContext.Request.Method,
            httpContext.Request.Path);

        httpContext.Response.StatusCode = StatusCodes.Status500InternalServerError;
        httpContext.Response.ContentType = "application/problem+json";

        await httpContext.Response.WriteAsJsonAsync(
            new ProblemDetails
            {
                Status = StatusCodes.Status500InternalServerError,
                Title = "An unexpected error occurred.",
                Type = "https://tools.ietf.org/html/rfc9457",
                // Deliberately no Detail: any per-exception detail risks leaking internal state.
            },
            cancellationToken);

        return true;
    }
}
