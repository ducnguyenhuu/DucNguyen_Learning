using Microsoft.AspNetCore.Http;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;
using Identity.Application.Abstractions;
using Identity.Domain.Abstractions;
using Identity.Infrastructure.Persistence;
using Identity.Infrastructure.Security;

namespace Identity.Api.Middleware;

/// <summary>
/// The single seam that proves the caller is a member (ADR-025). Looks up the authenticated
/// caller (identified by the token's <c>(tid, oid)</c> claim pair) and their active membership.
/// Only if both exist does it populate <see cref="HttpContextCallerContext"/> for the rest of the
/// request; otherwise it refuses with 403 — the caller is authenticated, but not a member.
/// </summary>
/// <remarks>
/// <para>
/// <b>Why an <see cref="IEndpointFilter"/>, not classic middleware:</b> applying this seam is an
/// explicit, opt-in choice per route group (<see cref="MembershipResolutionEndpointConventionBuilderExtensions.RequireMembership(RouteGroupBuilder)"/>).
/// <c>GET /me</c>, <c>POST /members/bootstrap</c> and <c>POST /invitations/{token}/accept</c> must
/// not run it, because their caller may not be a member yet. Opting in structurally (you either
/// add the filter to a route group or you don't) avoids a maintained exclusion list in global
/// middleware.
/// </para>
/// <para>
/// <b>403, not 404.</b> Under ADR-017 a non-member got 404 so a tenant's existence could not be
/// probed. With one organization there is nothing to hide, and 403 tells the caller exactly what
/// is wrong.
/// </para>
/// </remarks>
public sealed class MembershipResolutionFilter : IEndpointFilter
{
    private readonly ILogger<MembershipResolutionFilter> _logger;

    public MembershipResolutionFilter(ILogger<MembershipResolutionFilter> logger)
    {
        _logger = logger;
    }

    /// <inheritdoc />
    public async ValueTask<object?> InvokeAsync(
        EndpointFilterInvocationContext context,
        EndpointFilterDelegate next)
    {
        var httpContext = context.HttpContext;

        // The caller's identity comes only from the validated token's claims, never from
        // anything client-supplied in the request itself. MapInboundClaims = false means these
        // are literally "tid"/"oid" — not the legacy WS-Fed claim URIs.
        var tidClaim = httpContext.User.FindFirst("tid")?.Value;
        var oidClaim = httpContext.User.FindFirst("oid")?.Value;
        if (!Guid.TryParse(tidClaim, out var entraTenantId) ||
            !Guid.TryParse(oidClaim, out var entraObjectId))
        {
            // Authentication should already reject a request with no valid token before this
            // filter runs. If we still land here without usable identity claims, fail closed
            // rather than crash or leak anything.
            return NotMember("unusable identity claims");
        }

        var dbContext = httpContext.RequestServices.GetRequiredService<IdentityDbContext>();

        // A user that doesn't exist yet (first-ever request from this identity) is "no
        // membership" — JIT provisioning is EnsureUserProvisioned's concern, not this filter's.
        var user = await dbContext.Users
            .AsNoTracking()
            .SingleOrDefaultAsync(u => u.EntraTenantId == entraTenantId && u.EntraObjectId == entraObjectId);

        if (user is null)
        {
            return NotMember("no provisioned user for caller identity");
        }

        var membership = await dbContext.Memberships
            .AsNoTracking()
            .SingleOrDefaultAsync(m => m.UserId == user.Id && m.Status == MembershipStatus.Active);

        if (membership is null)
        {
            return NotMember("no active membership for caller");
        }

        // Only now — membership proven — does the caller context become real for the rest of
        // the request. The concrete implementation is scoped DI, so this is visible to
        // everything else resolved from this request's service provider.
        var callerContext = (HttpContextCallerContext)httpContext.RequestServices
            .GetRequiredService<ICallerContext>();
        callerContext.Resolve(user.Id, membership.Role);

        _logger.LogInformation(
            "Membership resolved: user {UserId} with role {Role}",
            user.Id,
            membership.Role);

        return await next(context);
    }

    /// <summary>
    /// The single failure response for every "not a member" outcome: unusable claims, an
    /// identity never seen before, or a user with no active membership. The reason is logged for
    /// operators but never reflected in the response.
    /// </summary>
    private object NotMember(string reason)
    {
        _logger.LogInformation("Membership resolution failed: {Reason}", reason);

        return Results.Forbid();
    }
}

/// <summary>
/// Opt-in wiring for <see cref="MembershipResolutionFilter"/>. Deliberately not a global
/// <c>app.Use(...)</c>: member-only route groups wire this by calling this extension once on the
/// group, not endpoint by endpoint.
/// </summary>
public static class MembershipResolutionEndpointConventionBuilderExtensions
{
    /// <summary>
    /// Adds <see cref="MembershipResolutionFilter"/> to the given route group.
    /// </summary>
    public static RouteGroupBuilder RequireMembership(this RouteGroupBuilder builder)
    {
        builder.AddEndpointFilter<MembershipResolutionFilter>();
        return builder;
    }

    /// <summary>
    /// Adds <see cref="MembershipResolutionFilter"/> to a single endpoint. Prefer
    /// <see cref="RequireMembership(RouteGroupBuilder)"/> on a route group when wiring multiple
    /// member-only endpoints at once.
    /// </summary>
    public static RouteHandlerBuilder RequireMembership(this RouteHandlerBuilder builder)
    {
        builder.AddEndpointFilter<MembershipResolutionFilter>();
        return builder;
    }
}
