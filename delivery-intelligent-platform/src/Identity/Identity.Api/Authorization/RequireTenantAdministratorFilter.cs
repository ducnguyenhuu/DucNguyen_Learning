using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Http;

namespace Identity.Api.Authorization;

/// <summary>
/// T088's wiring for the <c>TenantAdministrator</c> policy (T085). Deliberately an
/// <see cref="IEndpointFilter"/>, not an <c>[Authorize(Policy = "TenantAdministrator")]</c>
/// attribute — see <see cref="AdministratorOnlyAuthorizationHandler"/>'s remarks for the full
/// hazard this avoids: <c>TenantContextResolutionMiddleware</c> (T035) is itself an endpoint
/// filter, opted in per route via <c>.WithTenantContextResolution()</c>, and endpoint filters run
/// during endpoint invocation — strictly <b>after</b> ASP.NET Core's <c>UseAuthorization()</c>
/// middleware has already evaluated any <c>[Authorize(Policy=...)]</c> attribute. Using the
/// attribute here would evaluate <see cref="AdministratorOnlyAuthorizationHandler"/> before
/// <c>ITenantContext.Role</c> is ever populated, and every such request would fail closed on that
/// handler's "not resolved" exception — not because the caller lacks the role, but because the
/// check ran too early.
/// </summary>
/// <remarks>
/// This filter must be chained <b>after</b> <c>.WithTenantContextResolution()</c> in the
/// route-building fluent chain (mirroring <c>.WithIdempotency()</c>'s established opt-in-per-route
/// pattern from T056), so that by the time this filter's explicit
/// <see cref="IAuthorizationService.AuthorizeAsync(System.Security.Claims.ClaimsPrincipal, object)"/>
/// call reaches <see cref="AdministratorOnlyAuthorizationHandler"/>, <c>ITenantContext.Role</c> is
/// guaranteed already resolved.
/// </remarks>
public sealed class RequireTenantAdministratorFilter : IEndpointFilter
{
    /// <summary>The policy name registered for <see cref="AdministratorOnlyRequirement"/> (T085).</summary>
    public const string PolicyName = "TenantAdministrator";

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
/// Opt-in wiring for <see cref="RequireTenantAdministratorFilter"/>. Deliberately not blanket
/// middleware — applied per-endpoint/route-group at wiring time (T088), following T035's/T056's
/// established <c>WithTenantContextResolution</c>/<c>WithIdempotency</c> opt-in pattern. Must
/// always be chained after <c>.WithTenantContextResolution()</c> — see this filter's own remarks.
/// </summary>
public static class RequireTenantAdministratorEndpointConventionBuilderExtensions
{
    /// <summary>
    /// Adds <see cref="RequireTenantAdministratorFilter"/> to the given route group. Only call
    /// this on route groups already opted into <c>WithTenantContextResolution()</c>, and add it
    /// after that call in the chain.
    /// </summary>
    public static RouteGroupBuilder RequireTenantAdministrator(this RouteGroupBuilder builder)
    {
        builder.AddEndpointFilter<RequireTenantAdministratorFilter>();
        return builder;
    }

    /// <summary>
    /// Adds <see cref="RequireTenantAdministratorFilter"/> to a single endpoint. Only call this
    /// on endpoints already opted into <c>WithTenantContextResolution()</c>, and add it after that
    /// call in the chain.
    /// </summary>
    public static RouteHandlerBuilder RequireTenantAdministrator(this RouteHandlerBuilder builder)
    {
        builder.AddEndpointFilter<RequireTenantAdministratorFilter>();
        return builder;
    }
}
