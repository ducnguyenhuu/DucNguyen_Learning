using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Http;

namespace Identity.Api.Authorization;

/// <summary>
/// Wiring for the <c>Administrator</c> policy. Deliberately an <see cref="IEndpointFilter"/>, not
/// an <c>[Authorize(Policy = "Administrator")]</c> attribute — see
/// <see cref="AdministratorOnlyAuthorizationHandler"/>'s remarks for the full hazard this avoids:
/// <c>MembershipResolutionFilter</c> is itself an endpoint filter, opted in per route via
/// <c>.RequireMembership()</c>, and endpoint filters run during endpoint invocation — strictly
/// <b>after</b> ASP.NET Core's <c>UseAuthorization()</c> middleware has already evaluated any
/// <c>[Authorize(Policy=...)]</c> attribute. Using the attribute here would evaluate
/// <see cref="AdministratorOnlyAuthorizationHandler"/> before <c>ICallerContext.Role</c> is ever
/// populated, and every such request would fail closed on that handler's "not resolved"
/// exception — not because the caller lacks the role, but because the check ran too early.
/// </summary>
/// <remarks>
/// This filter must be chained <b>after</b> <c>.RequireMembership()</c> in the route-building
/// fluent chain (mirroring <c>.WithIdempotency()</c>'s opt-in-per-route pattern), so that by the
/// time this filter's explicit
/// <see cref="IAuthorizationService.AuthorizeAsync(System.Security.Claims.ClaimsPrincipal, object)"/>
/// call reaches <see cref="AdministratorOnlyAuthorizationHandler"/>, <c>ICallerContext.Role</c> is
/// guaranteed already resolved.
/// </remarks>
public sealed class RequireAdministratorFilter : IEndpointFilter
{
    /// <summary>The policy name registered for <see cref="AdministratorOnlyRequirement"/>.</summary>
    public const string PolicyName = "Administrator";

    /// <inheritdoc />
    public async ValueTask<object?> InvokeAsync(
        EndpointFilterInvocationContext context,
        EndpointFilterDelegate next)
    {
        var httpContext = context.HttpContext;
        var authorizationService = httpContext.RequestServices.GetRequiredService<IAuthorizationService>();

        var result = await authorizationService.AuthorizeAsync(httpContext.User, PolicyName);
        if (!result.Succeeded)
        {
            return Results.Forbid();
        }

        return await next(context);
    }
}

/// <summary>
/// Opt-in wiring for <see cref="RequireAdministratorFilter"/>. Deliberately not blanket
/// middleware — applied per-endpoint/route-group at wiring time, following the same opt-in
/// pattern as <c>RequireMembership</c>/<c>WithIdempotency</c>. Must always be chained after
/// <c>.RequireMembership()</c> — see this filter's own remarks.
/// </summary>
public static class RequireAdministratorEndpointConventionBuilderExtensions
{
    /// <summary>
    /// Adds <see cref="RequireAdministratorFilter"/> to the given route group. Only call this on
    /// route groups already opted into <c>RequireMembership()</c>, and add it after that call in
    /// the chain.
    /// </summary>
    public static RouteGroupBuilder RequireAdministrator(this RouteGroupBuilder builder)
    {
        builder.AddEndpointFilter<RequireAdministratorFilter>();
        return builder;
    }

    /// <summary>
    /// Adds <see cref="RequireAdministratorFilter"/> to a single endpoint. Only call this on
    /// endpoints already opted into <c>RequireMembership()</c>, and add it after that call in the
    /// chain.
    /// </summary>
    public static RouteHandlerBuilder RequireAdministrator(this RouteHandlerBuilder builder)
    {
        builder.AddEndpointFilter<RequireAdministratorFilter>();
        return builder;
    }
}
