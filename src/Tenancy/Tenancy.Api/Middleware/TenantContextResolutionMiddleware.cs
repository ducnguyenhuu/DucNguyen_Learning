using System.Diagnostics;
using Microsoft.AspNetCore.Http;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;
using Tenancy.Domain.Abstractions;
using Tenancy.Domain.Memberships;
using Tenancy.Infrastructure.Persistence;
using Tenancy.Infrastructure.Security;

namespace Tenancy.Api.Middleware;

/// <summary>
/// ADR-017's single tenant context resolution seam. Treats the <c>{tenantId}</c> route value as
/// an unproven <b>candidate</b> — never a grant — and proves it by looking up an active
/// <see cref="Membership"/> for the authenticated caller (identified by the token's
/// <c>(tid, oid)</c> claim pair) in that candidate tenant. Only if that lookup succeeds does it
/// populate <see cref="HttpContextTenantContext"/> for the rest of the request; otherwise it
/// fails closed with an indistinguishable 404 (FR-009) — the same response whether the tenant
/// doesn't exist, the id is malformed, or the caller simply isn't a member.
/// </summary>
/// <remarks>
/// <para>
/// <b>Why this is an <see cref="IEndpointFilter"/>, not classic pre-routing middleware:</b>
/// <c>{tenantId}</c> is a route parameter, and route values are only populated by ASP.NET Core
/// once endpoint routing has matched a request to an endpoint — i.e. only after
/// <c>UseRouting</c> has run internally. Both classic middleware registered late in the pipeline
/// (after routing/auth) *and* an endpoint filter can read the matched route value at that point,
/// so raw availability does not decide the question. What does: ADR-017 point 6 requires that
/// applying this seam be an <b>explicit, opt-in choice per endpoint/route-group</b> — it must
/// never run on <c>POST /tenants</c>, <c>GET /tenants</c>, or the invitation-accept endpoint,
/// none of which have a resolvable tenant. Classic middleware is registered globally in
/// <c>Program.cs</c>'s pipeline; making it conditional would mean either an <c>app.UseWhen(...)</c>
/// path-prefix check (a string convention silently relied upon everywhere, and exactly the kind
/// of "remember to exclude it" mechanism ADR-017 rejects) or checking route metadata by hand
/// inside the middleware body. <see cref="IEndpointFilter"/>, by contrast, is opted into
/// per-endpoint via <c>AddEndpointFilter</c>/<c>WithTenantContextResolution</c> on exactly the
/// route groups that declare a <c>{tenantId}</c> segment — the opt-in is structural (you either
/// add the filter to an endpoint's building or you don't), not a maintained exclusion list. That
/// directly serves ADR-017's compliance requirement that a fourth exception can't be added by
/// accident. Filters also run after routing has selected the endpoint, so
/// <c>context.HttpContext.GetRouteValue("tenantId")</c> is populated and reliable at the point
/// this filter executes — verified by reading <c>Microsoft.AspNetCore.Routing</c>'s endpoint
/// invocation pipeline, which resolves route values before invoking any endpoint filter.
/// </para>
/// <para>
/// <b>Resolution order (the chicken-and-egg fix):</b> a membership lookup needs
/// <see cref="TenancyDbContext"/>'s <c>"TenantFilter"</c> to be scoped to the tenant being
/// looked up in, but that filter reads <see cref="TenancyDbContext.CurrentTenantId"/> — which is
/// exactly what resolution is trying to determine. This filter breaks the cycle by setting
/// <see cref="TenancyDbContext.CurrentTenantId"/> to the unproven <b>candidate</b> first, purely
/// to scope the one lookup query that proves (or disproves) it. This is safe only because
/// nothing has been exposed to the rest of the request yet: if the membership lookup fails,
/// this filter short-circuits before <c>next()</c> is ever invoked, so no handler, repository,
/// or downstream code ever observes a <see cref="TenancyDbContext"/> scoped to an unproven
/// tenant.
/// </para>
/// </remarks>
public sealed class TenantContextResolutionMiddleware : IEndpointFilter
{
    /// <summary>
    /// The route parameter name this filter reads as the tenant candidate. Endpoint route
    /// templates that opt into this filter must declare a segment with this exact name
    /// (e.g. <c>/tenants/{tenantId}/...</c>), per ADR-017.
    /// </summary>
    public const string RouteParameterName = "tenantId";

    private readonly ILogger<TenantContextResolutionMiddleware> _logger;

    public TenantContextResolutionMiddleware(ILogger<TenantContextResolutionMiddleware> logger)
    {
        _logger = logger;
    }

    /// <inheritdoc />
    public async ValueTask<object?> InvokeAsync(
        EndpointFilterInvocationContext context,
        EndpointFilterDelegate next)
    {
        var httpContext = context.HttpContext;

        // Step 1: {tenantId} is a candidate only. An invalid GUID is treated identically to "no
        // membership found" below — both are indistinguishable 404s (FR-009).
        var routeValue = httpContext.GetRouteValue(RouteParameterName) as string;
        if (routeValue is null || !Guid.TryParse(routeValue, out var candidateGuid))
        {
            return NotMember(routeValue ?? "(missing)", "malformed tenant id");
        }

        var candidateTenantId = new TenantId(candidateGuid);

        // Step 2: the caller's identity comes only from the validated token's claims, never from
        // anything client-supplied in the request itself. MapInboundClaims = false (T032) means
        // these are literally "tid"/"oid" — not the legacy WS-Fed claim URIs.
        var tidClaim = httpContext.User.FindFirst("tid")?.Value;
        var oidClaim = httpContext.User.FindFirst("oid")?.Value;
        if (!Guid.TryParse(tidClaim, out var entraTenantId) ||
            !Guid.TryParse(oidClaim, out var entraObjectId))
        {
            // Authentication/authorization middleware ordering should already reject a request
            // with no valid token before this filter ever runs. If we still land here without
            // usable identity claims, fail the same closed way rather than crash or leak
            // anything — this is not a distinct error path.
            return NotMember(candidateTenantId.Value.ToString(), "unusable identity claims");
        }

        var dbContext = httpContext.RequestServices.GetRequiredService<TenancyDbContext>();

        // Step 3: set CurrentTenantId to the candidate — "trust it just enough to scope the one
        // lookup that proves or disproves it." Nothing downstream is exposed yet: next() has not
        // been called, so no handler can observe this DbContext scoped to an unproven tenant.
        dbContext.CurrentTenantId = candidateTenantId;

        // User lookup does NOT go through the tenant filter: User does not implement
        // ITenantOwned (confirmed by reading Tenancy.Domain.Users.User), so this composite
        // lookup by Entra identity is unaffected by CurrentTenantId either way. A user that
        // doesn't exist yet (first-ever request from this identity) is "no membership" — JIT
        // provisioning is T036's concern, not this filter's.
        var user = await dbContext.Users
            .AsNoTracking()
            .SingleOrDefaultAsync(u => u.EntraTenantId == entraTenantId && u.EntraObjectId == entraObjectId);

        if (user is null)
        {
            return NotMember(candidateTenantId.Value.ToString(), "no provisioned user for caller identity");
        }

        // Step 4: Membership IS ITenantOwned, so this query is scoped by the "TenantFilter" to
        // CurrentTenantId (the candidate) automatically — plus the caller's own UserId and
        // Active status, per ADR-017's "active membership" requirement.
        var membership = await dbContext.Memberships
            .AsNoTracking()
            .SingleOrDefaultAsync(m => m.UserId == user.Id && m.Status == MembershipStatus.Active);

        if (membership is null)
        {
            return NotMember(candidateTenantId.Value.ToString(), "no active membership for caller in candidate tenant");
        }

        // Only now — membership proven — does the tenant context become real for the rest of
        // the request. The concrete implementation is scoped DI, so this is visible to
        // everything else resolved from this request's service provider.
        var tenantContext = (HttpContextTenantContext)httpContext.RequestServices
            .GetRequiredService<Tenancy.Application.Abstractions.ITenantContext>();
        tenantContext.Resolve(candidateTenantId, membership.Role);

        _logger.LogInformation(
            "Membership resolved for tenant {TenantId}: user {UserId} with role {Role}",
            candidateTenantId,
            user.Id,
            membership.Role);

        // FR-004's tenant-identity enrichment half (T022): tenant identity is only known from
        // this point on, so it is tagged/scoped here — nested inside the user-id scope
        // UserIdentityEnrichmentMiddleware already pushed further up the pipeline — rather than
        // in classic middleware, which cannot see this filter's resolved TenantId at all.
        Activity.Current?.SetTag("tenant.id", candidateTenantId.Value.ToString());

        var tenantLogger = httpContext.RequestServices
            .GetRequiredService<ILoggerFactory>()
            .CreateLogger(typeof(TenantContextResolutionMiddleware).FullName!);

        using (tenantLogger.BeginScope(
            new Dictionary<string, object?> { ["TenantId"] = candidateTenantId.Value.ToString() }))
        {
            return await next(context);
        }
    }

    /// <summary>
    /// The single failure response for every "not a member" outcome — malformed id, nonexistent
    /// tenant, unknown user, or a real member with no active membership in this tenant. FR-009
    /// requires all four to be byte-for-byte indistinguishable, so this returns a bare 404 with
    /// no body and no detail describing which case occurred. <c>403</c> is deliberately never
    /// used here: per ADR-017, <c>403</c> would itself confirm the tenant exists.
    /// </summary>
    private object NotMember(string candidateTenantId, string reason)
    {
        // ADR-017's indistinguishability requirement is about the HTTP response, not
        // server-side logs — operators legitimately need to know *why* resolution failed for
        // debugging, so the reason is logged here but never reflected in the 404 response body
        // that Results.NotFound() below returns.
        _logger.LogInformation(
            "Membership resolution failed for candidate tenant {CandidateTenantId}: {Reason}",
            candidateTenantId,
            reason);

        return Results.NotFound();
    }
}

/// <summary>
/// Opt-in wiring for <see cref="TenantContextResolutionMiddleware"/>. Deliberately not a global
/// <c>app.Use(...)</c>: ADR-017 requires this seam be applied per tenant-scoped route group, and
/// never to the three enumerated exceptions (<c>POST /tenants</c>, <c>GET /tenants</c>,
/// <c>POST /invitations/{token}/accept</c>), none of which have a <c>{tenantId}</c> segment to
/// resolve in the first place. Phase 3 tasks (T044+) wire tenant-scoped route groups by calling
/// this extension once on the group, not by adding it endpoint-by-endpoint.
/// </summary>
public static class TenantContextResolutionEndpointConventionBuilderExtensions
{
    /// <summary>
    /// Adds ADR-017's tenant context resolution filter to the given route group. Only call this
    /// on route groups whose endpoints declare a <c>{tenantId}</c> route parameter.
    /// </summary>
    public static RouteGroupBuilder WithTenantContextResolution(this RouteGroupBuilder builder)
    {
        builder.AddEndpointFilter<TenantContextResolutionMiddleware>();
        return builder;
    }

    /// <summary>
    /// Adds ADR-017's tenant context resolution filter to a single endpoint. Prefer
    /// <see cref="WithTenantContextResolution(RouteGroupBuilder)"/> on a route group when wiring
    /// multiple tenant-scoped endpoints at once, so the opt-in is made once, not per-endpoint.
    /// </summary>
    public static RouteHandlerBuilder WithTenantContextResolution(this RouteHandlerBuilder builder)
    {
        builder.AddEndpointFilter<TenantContextResolutionMiddleware>();
        return builder;
    }
}
