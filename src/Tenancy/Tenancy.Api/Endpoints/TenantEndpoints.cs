using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using Tenancy.Api.ETags;
using Tenancy.Api.Idempotency;
using Tenancy.Api.Middleware;
using Tenancy.Application.Abstractions;
using Tenancy.Application.Tenants;
using Tenancy.Application.Users;
using Tenancy.Domain.Abstractions;
using Tenancy.Domain.Tenants;
using Tenancy.Infrastructure.Persistence;

namespace Tenancy.Api.Endpoints;

/// <summary>
/// T058 — the four <c>/tenants</c> endpoints, wiring together every seam built in T032-T057:
/// authentication (T032), JIT user provisioning (T036), ADR-017 tenant context resolution
/// (T035), the idempotency filter (T056), ETag/If-Match handling (T057), and the
/// CreateTenant/GetTenant/RenameTenant/ListTenants use cases (T054/T055).
/// </summary>
/// <remarks>
/// <para>
/// <b>412 vs 409 on PATCH.</b> Both are the same CLR exception
/// (<see cref="DbUpdateConcurrencyException"/>) thrown by the same call
/// (<c>SaveChangesAsync</c>), so the distinction cannot be read off the exception itself. This
/// endpoint distinguishes them by comparing the caller's decoded <c>If-Match</c> bytes against a
/// fresh, pre-update read of the row's actual <c>RowVersion</c>, taken immediately before the
/// rename/save attempt:
/// </para>
/// <list type="bullet">
/// <item>
/// If the decoded <c>If-Match</c> already does not match that fresh read, the caller's view was
/// stale <b>before this request even tried to write</b> — a normal "someone else changed it since
/// you last read it" case. That is <c>412 Precondition Failed</c>, and in this case the endpoint
/// never needs to reach <c>SaveChangesAsync</c> at all to know the outcome.
/// </item>
/// <item>
/// If the decoded <c>If-Match</c> DOES match that fresh read, but
/// <see cref="DbUpdateConcurrencyException"/> is still thrown when saving, then someone else's
/// write landed in the narrow window between this request's fresh read and its own save — a
/// genuine race at save time. That is <c>409 Conflict</c>.
/// </item>
/// </list>
/// <para>
/// This is not a perfect closure of the race window (a fresh read immediately followed by a
/// concurrency-checked save still has a — much narrower — window of its own), but it is the
/// distinguishing signal T058's brief calls for, and matches T051's own test framing ("stale →
/// 412, race at save → 409").
/// </para>
/// </remarks>
public static class TenantEndpoints
{
    public static IEndpointRouteBuilder MapTenantEndpoints(this IEndpointRouteBuilder app)
    {
        // ADR-017 exceptions 1 and 2: POST /tenants and GET /tenants have no {tenantId} segment
        // to resolve, so neither opts into WithTenantContextResolution().
        var tenants = app.MapGroup("/tenants");

        // Ordering matters: T056's IdempotencyFilter resolves the caller's UserId (to build its
        // cache key) by looking up an *already-existing* User row — it does not JIT-provision.
        // POST /tenants is exactly the route where a brand-new identity's first-ever request
        // has no User row yet (see this class's remarks on ProvisionCallerAsync), so without a
        // provisioning step running strictly before the idempotency filter, that lookup would
        // always miss for a first-time caller and the filter would reject with 401 before the
        // handler (which does its own provisioning) ever ran. AddEndpointFilter<T> registrations
        // run in the order added, each wrapping the ones after — JitProvisionCallerFilter is
        // added first so it provisions before WithIdempotency()'s filter ever tries to resolve
        // the caller.
        tenants.MapPost("/", CreateTenantAsync)
            .RequireAuthorization()
            .AddEndpointFilter<JitProvisionCallerFilter>()
            .WithIdempotency();

        tenants.MapGet("/", ListTenantsAsync)
            .RequireAuthorization();

        // Tenant-scoped: both opt into T035's resolution filter.
        var scopedTenant = app.MapGroup("/tenants/{tenantId}")
            .RequireAuthorization()
            .WithTenantContextResolution();

        scopedTenant.MapGet("/", GetTenantAsync);
        scopedTenant.MapPatch("/", PatchTenantAsync);

        return app;
    }

    private static async Task<IResult> CreateTenantAsync(
        HttpContext httpContext,
        CreateTenantRequest request,
        EnsureUserProvisioned ensureUserProvisioned,
        CreateTenant createTenant,
        CancellationToken ct)
    {
        var caller = await ProvisionCallerAsync(httpContext, ensureUserProvisioned, ct);
        if (caller is null)
        {
            return Results.Problem(
                title: "Caller could not be resolved",
                detail: "No usable identity claims were present on the token.",
                statusCode: StatusCodes.Status401Unauthorized);
        }

        Tenant tenant;
        try
        {
            tenant = await createTenant.ExecuteAsync(request.DisplayName, caller.Id, ct);
        }
        catch (DomainException ex)
        {
            return Results.Problem(
                title: "Invalid tenant",
                detail: ex.Message,
                statusCode: StatusCodes.Status400BadRequest);
        }

        var dto = TenantDto.FromDomain(tenant);

        return Results.Created($"/tenants/{tenant.Id.Value}", dto)
            .WithHeader("ETag", RowVersionETag.ToETag(tenant.RowVersion));
    }

    private static async Task<IResult> ListTenantsAsync(
        HttpContext httpContext,
        EnsureUserProvisioned ensureUserProvisioned,
        ListTenants listTenants,
        IMembershipDirectory membershipDirectory,
        CancellationToken ct)
    {
        var caller = await ProvisionCallerAsync(httpContext, ensureUserProvisioned, ct);
        if (caller is null)
        {
            return Results.Problem(
                title: "Caller could not be resolved",
                detail: "No usable identity claims were present on the token.",
                statusCode: StatusCodes.Status401Unauthorized);
        }

        // ListTenants (T055) returns the caller's Tenant rows but not their per-tenant Role, and
        // openapi.yaml's TenantSummary schema requires one — re-fetch the caller's own
        // memberships (the one sanctioned cross-tenant read, T037) to build the tenantId->role
        // lookup this response shape needs. Both calls are cheap, tenant-count-bounded reads.
        var memberships = await membershipDirectory.GetMembershipsForUserAsync(caller.Id, ct);
        var roleByTenantId = memberships.ToDictionary(m => m.TenantId, m => m.Role);

        var tenantList = await listTenants.ExecuteAsync(caller.Id, ct);

        var summaries = tenantList
            .Select(t => new TenantSummaryDto(
                t.Id.Value,
                t.DisplayName,
                roleByTenantId.TryGetValue(t.Id, out var role) ? role.ToString() : Role.Member.ToString()))
            .ToList();

        return Results.Ok(summaries);
    }

    private static async Task<IResult> GetTenantAsync(GetTenant getTenant, CancellationToken ct)
    {
        var tenant = await getTenant.ExecuteAsync(ct);
        if (tenant is null)
        {
            // Shouldn't happen: T035's filter already proved membership in this candidate
            // tenant before this handler ever runs. Defend against it the same closed way T035
            // itself does, rather than leak anything more specific.
            return Results.NotFound();
        }

        var dto = TenantDto.FromDomain(tenant);
        return Results.Ok(dto).WithHeader("ETag", RowVersionETag.ToETag(tenant.RowVersion));
    }

    private static async Task<IResult> PatchTenantAsync(
        HttpContext httpContext,
        RenameTenantRequest request,
        RenameTenant renameTenant,
        TenancyDbContext dbContext,
        CancellationToken ct)
    {
        if (!httpContext.Request.Headers.TryGetValue("If-Match", out var ifMatchValues) ||
            string.IsNullOrWhiteSpace(ifMatchValues.ToString()))
        {
            return Results.Problem(
                title: "If-Match header required",
                detail: "This operation requires an If-Match header naming the version being updated.",
                statusCode: StatusCodes.Status428PreconditionRequired);
        }

        byte[] decodedIfMatch;
        try
        {
            decodedIfMatch = RowVersionETag.FromIfMatch(ifMatchValues.ToString());
        }
        catch (FormatException ex)
        {
            return Results.Problem(
                title: "Malformed If-Match header",
                detail: ex.Message,
                statusCode: StatusCodes.Status400BadRequest);
        }

        // Fresh, pre-update read of the row's actual current RowVersion — the "did the caller's
        // If-Match already not match at request start" signal the 412-vs-409 distinction (see
        // this class's remarks) depends on. This is deliberately a second, tracked load (not
        // reused from GetTenant), because RenameTenant's own load below is what actually gets
        // mutated and saved.
        var tenant = await dbContext.Tenants
            .AsNoTracking()
            .SingleOrDefaultAsync(t => t.Id == dbContext.CurrentTenantId, ct);

        if (tenant is null)
        {
            return Results.NotFound();
        }

        if (!decodedIfMatch.AsSpan().SequenceEqual(tenant.RowVersion))
        {
            // Already stale relative to what a fresh read shows, before any write was attempted.
            return Results.Problem(
                title: "Precondition failed",
                detail: "The supplied If-Match value is stale.",
                statusCode: StatusCodes.Status412PreconditionFailed);
        }

        Tenant? updated;
        try
        {
            updated = await RenameWithOriginalRowVersionAsync(
                dbContext, renameTenant, decodedIfMatch, request.DisplayName, ct);
        }
        catch (DomainException ex)
        {
            return Results.Problem(
                title: "Invalid tenant",
                detail: ex.Message,
                statusCode: StatusCodes.Status400BadRequest);
        }
        catch (DbUpdateConcurrencyException)
        {
            // The If-Match value matched a fresh read moments ago, yet the save still lost the
            // optimistic-concurrency check: someone else's write landed in between. A genuine
            // race at save time, not a stale caller.
            return Results.Problem(
                title: "Concurrency conflict",
                detail: "The tenant was modified by another request while this update was in flight.",
                statusCode: StatusCodes.Status409Conflict);
        }

        if (updated is null)
        {
            return Results.NotFound();
        }

        var dto = TenantDto.FromDomain(updated);
        return Results.Ok(dto).WithHeader("ETag", RowVersionETag.ToETag(updated.RowVersion));
    }

    /// <summary>
    /// Loads the tenant via <see cref="ITenantRepository"/> exactly as <see cref="RenameTenant"/>
    /// would, but first pins the tracked entity's original <c>RowVersion</c> to the caller's
    /// decoded <c>If-Match</c> bytes (EF's concurrency-check baseline) before renaming/saving, per
    /// this task's brief.
    /// </summary>
    /// <remarks>
    /// <c>internal</c> rather than <c>private</c> (with <c>Tenancy.Api.csproj</c>'s existing
    /// <c>InternalsVisibleTo("Tenancy.IntegrationTests")</c>) solely so
    /// <c>ConcurrencyTests.RenameWithOriginalRowVersionAsync_SameValueAsCurrentDisplayName_StillThrowsOnStaleRowVersion</c>
    /// can exercise this exact method directly and deterministically. The bug this guards against
    /// (a stale pinned <c>RowVersion.OriginalValue</c> going unchecked when the requested value
    /// equals the tenant's current value) only manifests in a narrow window between
    /// <c>PatchTenantAsync</c>'s own fresh pre-check and this method's tracked load/save — not
    /// reliably reproducible from outside the process via real HTTP concurrency without a
    /// save-pipeline test hook (see <see cref="ConcurrencyTests"/>'s remarks on that same
    /// limitation for the save-time race case).
    /// </remarks>
    internal static async Task<Tenant?> RenameWithOriginalRowVersionAsync(
        TenancyDbContext dbContext,
        RenameTenant renameTenant,
        byte[] originalRowVersion,
        string newDisplayName,
        CancellationToken ct)
    {
        var tracked = await dbContext.Tenants
            .SingleOrDefaultAsync(t => t.Id == dbContext.CurrentTenantId, ct);

        if (tracked is null)
        {
            return null;
        }

        var trackedEntry = dbContext.Entry(tracked);
        trackedEntry.Property(nameof(Tenant.RowVersion)).OriginalValue = originalRowVersion;

        // Force a real UPDATE (and thus the optimistic-concurrency check against the pinned
        // OriginalValue above) even when the caller's requested displayName happens to equal the
        // tenant's current displayName: without this, EF's change tracker sees zero modified
        // scalar properties for a same-value "change" and skips SaveChanges' UPDATE entirely —
        // silently "succeeding" without the concurrency check ever running against the database
        // at all. Mirrors MemberEndpoints.PatchMemberRoleAsync's identical fix.
        trackedEntry.State = EntityState.Modified;

        return await renameTenant.ExecuteAsync(newDisplayName, ct);
    }

    /// <summary>
    /// JIT-provisions the caller (T036) from the validated token's <c>(tid, oid)</c> claims, with
    /// a best-effort email claim lookup. Test tokens (Tier 1 <c>TestAuthHandler</c> and Tier 2
    /// <c>SignedTokenHarness</c>) carry no email claim at all, so a deterministic placeholder is
    /// synthesized from the caller's <c>oid</c> when none is present — display/invitation-matching
    /// only (research.md R2), never an authorization input, so this placeholder is harmless.
    /// </summary>
    private static async Task<Domain.Users.User?> ProvisionCallerAsync(
        HttpContext httpContext, EnsureUserProvisioned ensureUserProvisioned, CancellationToken ct)
    {
        var tidClaim = httpContext.User.FindFirst("tid")?.Value;
        var oidClaim = httpContext.User.FindFirst("oid")?.Value;
        if (!Guid.TryParse(tidClaim, out var entraTenantId) || !Guid.TryParse(oidClaim, out var entraObjectId))
        {
            return null;
        }

        var emailClaim =
            httpContext.User.FindFirst("email")?.Value ??
            httpContext.User.FindFirst("preferred_username")?.Value ??
            httpContext.User.FindFirst("upn")?.Value;

        var email = new EmailAddress(
            string.IsNullOrWhiteSpace(emailClaim) ? $"{entraObjectId}@unresolved.invalid" : emailClaim);

        return await ensureUserProvisioned.ExecuteAsync(entraTenantId, entraObjectId, email, ct);
    }

    private static IResult WithHeader(this IResult result, string name, string value) =>
        new HeaderDecoratedResult(result, name, value);

    /// <summary>
    /// Wraps an inner <see cref="IResult"/> to add one response header when executed — used so
    /// <c>ETag</c> can be attached to <see cref="Results.Created"/>/<see cref="Results.Ok"/>
    /// without hand-rolling the whole response.
    /// </summary>
    private sealed class HeaderDecoratedResult : IResult
    {
        private readonly IResult _inner;
        private readonly string _headerName;
        private readonly string _headerValue;

        public HeaderDecoratedResult(IResult inner, string headerName, string headerValue)
        {
            _inner = inner;
            _headerName = headerName;
            _headerValue = headerValue;
        }

        public Task ExecuteAsync(HttpContext httpContext)
        {
            httpContext.Response.Headers[_headerName] = _headerValue;
            return _inner.ExecuteAsync(httpContext);
        }
    }
}

/// <summary>
/// Runs strictly before <see cref="Tenancy.Api.Idempotency.IdempotencyFilter"/> on <c>POST
/// /tenants</c> so that filter's own caller-resolution lookup (an existing-row-only
/// <c>FindByEntraIdentityAsync</c>, never a JIT-provisioning one) always has a row to find, even
/// for a brand-new identity's very first request. See <see cref="TenantEndpoints"/>'s remarks on
/// endpoint filter ordering for why this must be registered before <c>WithIdempotency()</c>.
/// </summary>
public sealed class JitProvisionCallerFilter : IEndpointFilter
{
    public async ValueTask<object?> InvokeAsync(
        EndpointFilterInvocationContext context, EndpointFilterDelegate next)
    {
        var httpContext = context.HttpContext;
        var ensureUserProvisioned = httpContext.RequestServices.GetRequiredService<EnsureUserProvisioned>();

        var tidClaim = httpContext.User.FindFirst("tid")?.Value;
        var oidClaim = httpContext.User.FindFirst("oid")?.Value;
        if (Guid.TryParse(tidClaim, out var entraTenantId) && Guid.TryParse(oidClaim, out var entraObjectId))
        {
            var emailClaim =
                httpContext.User.FindFirst("email")?.Value ??
                httpContext.User.FindFirst("preferred_username")?.Value ??
                httpContext.User.FindFirst("upn")?.Value;

            var email = new EmailAddress(
                string.IsNullOrWhiteSpace(emailClaim) ? $"{entraObjectId}@unresolved.invalid" : emailClaim);

            await ensureUserProvisioned.ExecuteAsync(entraTenantId, entraObjectId, email, httpContext.RequestAborted);
        }

        // If the claims are unusable, do nothing here — CreateTenantAsync's own
        // ProvisionCallerAsync call (and its 401 fallback) is still the source of truth for that
        // failure mode; this filter's only job is to make the *happy* path resolvable for
        // T056's filter.
        return await next(context);
    }
}

/// <summary>Request body for <c>POST /tenants</c>, per openapi.yaml.</summary>
public sealed record CreateTenantRequest(string DisplayName);

/// <summary>Request body for <c>PATCH /tenants/{tenantId}</c>, per openapi.yaml.</summary>
public sealed record RenameTenantRequest(string DisplayName);

/// <summary>The <c>Tenant</c> response schema per openapi.yaml.</summary>
public sealed record TenantDto(Guid Id, string DisplayName, string Status, DateTimeOffset CreatedAtUtc)
{
    public static TenantDto FromDomain(Tenant tenant) =>
        new(tenant.Id.Value, tenant.DisplayName, tenant.Status.ToString(), tenant.CreatedAtUtc);
}

/// <summary>The <c>TenantSummary</c> response schema per openapi.yaml.</summary>
public sealed record TenantSummaryDto(Guid Id, string DisplayName, string Role);
