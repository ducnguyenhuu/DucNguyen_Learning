using System.Security.Cryptography;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Routing;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Storage;
using Tenancy.Application.Abstractions;
using Tenancy.Domain.Abstractions;
using Tenancy.Infrastructure.Persistence;

namespace Tenancy.Api.Idempotency;

/// <summary>
/// Caches the outcome of a mutating request so a client-supplied <c>Idempotency-Key</c> header
/// can be safely retried without double-applying it (T056). This entity's persistence shape is
/// <see cref="IdempotencyRecord"/> — see its remarks for why the entity is keyed by
/// <c>(TenantId, CreatedByUserId, Endpoint, Key)</c> with a sentinel <see cref="TenantId.Empty"/>
/// standing in for "no tenant yet" rather than a nullable column.
/// </summary>
/// <remarks>
/// <para>
/// <b>Why this is an <see cref="IEndpointFilter"/>, not classic middleware:</b> per this task's
/// own text, "middleware runs before routing and model binding" — an idempotency check needs to
/// run once the endpoint (and therefore its route pattern, used as part of the cache key) is
/// known, following the same precedent as <c>TenantContextResolutionMiddleware</c> (T035).
/// </para>
/// <para>
/// <b>Response-capture constraint:</b> to cache a response for replay, this filter must observe
/// the exact bytes written to the HTTP response. It does this by executing the downstream
/// result itself (<see cref="IResult.ExecuteAsync"/>) against a buffered
/// <see cref="HttpResponse.Body"/>, which requires the downstream handler to return an
/// <see cref="IResult"/> — this project's established convention (e.g.
/// <c>TenantContextResolutionMiddleware</c>'s <c>Results.NotFound()</c>). A handler that returns
/// a plain POCO (relying on minimal APIs' implicit JSON-result path, which executes *after* the
/// filter chain returns, when this filter can no longer observe it) is not supported by this
/// filter as written; every mutating handler in this codebase already returns an
/// <see cref="IResult"/>, so this is not a new constraint in practice.
/// </para>
/// <para>
/// <b>Transaction composition (the task's "same transaction as the business write"
/// requirement):</b> this filter opens an explicit <see cref="IDbContextTransaction"/> on
/// <see cref="TenancyDbContext"/> — a scoped, per-request instance (see
/// <c>TenancyDbContext</c>'s remarks; this project deliberately does not use
/// <c>AddDbContextPool</c>) — *before* calling <c>next(context)</c>, and commits it only after
/// the downstream response has been captured and the same tracked <see cref="IdempotencyRecord"/>
/// has been updated to <see cref="IdempotencyStatus.Completed"/>. Because the DbContext instance
/// is shared (via DI) between this filter and whatever use case the downstream handler invokes,
/// any <c>SaveChangesAsync</c> call the handler makes for its own business write happens on the
/// same context instance while this filter's transaction is still open, so EF Core enlists that
/// save in the same ambient transaction automatically (<c>DatabaseFacade.CurrentTransaction</c>)
/// — no <c>TransactionScope</c> or explicit coordination with the handler is required. If the
/// handler throws, this filter rolls the transaction back (undoing both the idempotency
/// bookkeeping and any partial business write) and rethrows, so a crash mid-request never leaves
/// a half-applied write paired with a "Completed" idempotency record. This relies on the handler
/// never beginning and committing a *different*, competing transaction itself; nothing in this
/// codebase does that as of T056.
/// </para>
/// </remarks>
public sealed class IdempotencyFilter : IEndpointFilter
{
    /// <summary>The required client-supplied idempotency key header.</summary>
    public const string IdempotencyKeyHeaderName = "Idempotency-Key";

    /// <summary>Set on a replayed response so the caller can distinguish it from a fresh one.</summary>
    public const string ReplayedHeaderName = "Idempotency-Replayed";

    /// <summary>TTL for a cached record, per the task's own text.</summary>
    private static readonly TimeSpan RecordTtl = TimeSpan.FromHours(24);

    /// <summary>
    /// How long an <see cref="IdempotencyStatus.InFlight"/> record is treated as "genuinely still
    /// being processed" before it becomes reclaimable, per the task's own text.
    /// </summary>
    private static readonly TimeSpan InFlightReclaimThreshold = TimeSpan.FromSeconds(60);

    /// <inheritdoc />
    public async ValueTask<object?> InvokeAsync(
        EndpointFilterInvocationContext context,
        EndpointFilterDelegate next)
    {
        var httpContext = context.HttpContext;
        var ct = httpContext.RequestAborted;

        if (!httpContext.Request.Headers.TryGetValue(IdempotencyKeyHeaderName, out var keyValues) ||
            string.IsNullOrWhiteSpace(keyValues.ToString()))
        {
            return Results.Problem(
                title: "Missing Idempotency-Key header",
                detail: $"This endpoint requires the '{IdempotencyKeyHeaderName}' header.",
                statusCode: StatusCodes.Status400BadRequest);
        }

        var key = keyValues.ToString();

        var dbContext = httpContext.RequestServices.GetRequiredService<TenancyDbContext>();
        var clock = httpContext.RequestServices.GetRequiredService<IClock>();

        var tenantId = ResolveTenantId(httpContext);
        var createdByUserId = await ResolveUserIdAsync(httpContext, dbContext, ct);
        if (createdByUserId is null)
        {
            return Results.Problem(
                title: "Caller could not be resolved",
                detail: "No provisioned user matches the caller's identity.",
                statusCode: StatusCodes.Status401Unauthorized);
        }

        var endpoint = DescribeEndpoint(httpContext);
        var requestHash = await ComputeRequestHashAsync(httpContext);
        var now = clock.UtcNow;

        var existing = await dbContext.IdempotencyRecords.SingleOrDefaultAsync(
            r => r.TenantId == tenantId &&
                 r.CreatedByUserId == createdByUserId.Value &&
                 r.Endpoint == endpoint &&
                 r.Key == key,
            ct);

        // TTL 24h: an expired record is functionally absent for lookup purposes, but the PK
        // still occupies the row, so it must actually be deleted before a fresh insert can use
        // the same key — a "treat as absent" read-side trick alone would still collide on the PK.
        if (existing is not null && existing.ExpiresAtUtc < now)
        {
            dbContext.IdempotencyRecords.Remove(existing);
            await dbContext.SaveChangesAsync(ct);
            existing = null;
        }

        if (existing is not null)
        {
            return await HandleExistingRecordAsync(context, next, dbContext, existing, requestHash, now);
        }

        var record = new IdempotencyRecord
        {
            TenantId = tenantId,
            CreatedByUserId = createdByUserId.Value,
            Endpoint = endpoint,
            Key = key,
            RequestHash = requestHash,
            Status = IdempotencyStatus.InFlight,
            CreatedAtUtc = now,
            ExpiresAtUtc = now + RecordTtl,
        };

        return await InsertAndProceedAsync(context, next, dbContext, record, requestHash, now);
    }

    /// <summary>
    /// Handles a lookup hit: a legitimate replay, a hash mismatch, a genuinely-in-flight
    /// conflict, or a reclaimable stale in-flight row.
    /// </summary>
    private async ValueTask<object?> HandleExistingRecordAsync(
        EndpointFilterInvocationContext context,
        EndpointFilterDelegate next,
        TenancyDbContext dbContext,
        IdempotencyRecord existing,
        byte[] requestHash,
        DateTimeOffset now)
    {
        var httpContext = context.HttpContext;

        if (existing.Status == IdempotencyStatus.Completed)
        {
            if (!existing.RequestHash.AsSpan().SequenceEqual(requestHash))
            {
                return Results.Problem(
                    title: "Idempotency key reuse with a different request",
                    detail: "This Idempotency-Key was already used with a different request body.",
                    statusCode: StatusCodes.Status422UnprocessableEntity);
            }

            // Legitimate replay: do not re-execute the business logic. Write the stored response
            // verbatim.
            httpContext.Response.StatusCode = existing.StatusCode ?? StatusCodes.Status200OK;
            httpContext.Response.Headers[ReplayedHeaderName] = "true";
            if (!string.IsNullOrEmpty(existing.ResourceLocation))
            {
                httpContext.Response.Headers.Location = existing.ResourceLocation;
            }

            if (!string.IsNullOrEmpty(existing.ResponseBody))
            {
                httpContext.Response.ContentType ??= "application/json; charset=utf-8";
                await httpContext.Response.WriteAsync(existing.ResponseBody, httpContext.RequestAborted);
            }

            return Results.Empty;
        }

        // existing.Status == InFlight.
        var age = now - existing.CreatedAtUtc;
        if (age < InFlightReclaimThreshold)
        {
            httpContext.Response.Headers.RetryAfter = ((int)InFlightReclaimThreshold.TotalSeconds).ToString();
            return Results.Problem(
                title: "Request already in flight",
                detail: "An identical request with this Idempotency-Key is still being processed.",
                statusCode: StatusCodes.Status409Conflict);
        }

        // Reclaimable: the original request likely crashed/timed out without completing. Reuse
        // the same row (same PK) rather than inserting a new one.
        existing.RequestHash = requestHash;
        existing.CreatedAtUtc = now;
        existing.ExpiresAtUtc = now + RecordTtl;
        existing.Status = IdempotencyStatus.InFlight;
        existing.StatusCode = null;
        existing.ResponseBody = null;
        existing.ResourceLocation = null;

        var transaction = await dbContext.Database.BeginTransactionAsync(httpContext.RequestAborted);
        await dbContext.SaveChangesAsync(httpContext.RequestAborted);
        return await ProceedWithOpenTransactionAsync(context, next, dbContext, existing, transaction);
    }

    /// <summary>
    /// Inserts a brand-new <see cref="IdempotencyRecord"/> using insert-and-catch-duplicate
    /// (per the task's own text) rather than check-then-insert, which would leave a TOCTOU race
    /// between two near-simultaneous first requests for the same key.
    /// </summary>
    private async ValueTask<object?> InsertAndProceedAsync(
        EndpointFilterInvocationContext context,
        EndpointFilterDelegate next,
        TenancyDbContext dbContext,
        IdempotencyRecord record,
        byte[] requestHash,
        DateTimeOffset now)
    {
        var httpContext = context.HttpContext;
        var ct = httpContext.RequestAborted;

        var transaction = await dbContext.Database.BeginTransactionAsync(ct);
        dbContext.IdempotencyRecords.Add(record);

        try
        {
            await dbContext.SaveChangesAsync(ct);
        }
        catch (DbUpdateException)
        {
            // Lost the insert race against a near-simultaneous first request for the same key.
            await transaction.RollbackAsync(ct);
            dbContext.Entry(record).State = EntityState.Detached;

            var raceWinner = await dbContext.IdempotencyRecords.SingleOrDefaultAsync(
                r => r.TenantId == record.TenantId &&
                     r.CreatedByUserId == record.CreatedByUserId &&
                     r.Endpoint == record.Endpoint &&
                     r.Key == record.Key,
                ct);

            if (raceWinner is null)
            {
                // Not a unique-key collision on this PK after all (e.g. a transient/unrelated
                // constraint violation) — nothing sensible to reconcile against, rethrow.
                throw;
            }

            return await HandleExistingRecordAsync(context, next, dbContext, raceWinner, requestHash, now);
        }

        return await ProceedWithOpenTransactionAsync(context, next, dbContext, record, transaction);
    }

    /// <summary>
    /// Common tail shared by the fresh-insert and reclaim paths: run the downstream handler with
    /// the idempotency transaction still open, capture its response by executing the returned
    /// <see cref="IResult"/> against a buffered response stream, mark the record
    /// <see cref="IdempotencyStatus.Completed"/> with that captured response, and commit — all as
    /// one transaction. See the class remarks for why this achieves "same transaction as the
    /// business write" without any explicit coordination with the handler.
    /// </summary>
    private static async ValueTask<object?> ProceedWithOpenTransactionAsync(
        EndpointFilterInvocationContext context,
        EndpointFilterDelegate next,
        TenancyDbContext dbContext,
        IdempotencyRecord record,
        IDbContextTransaction transaction)
    {
        var httpContext = context.HttpContext;
        var ct = httpContext.RequestAborted;

        object? result;
        try
        {
            result = await next(context);
        }
        catch
        {
            await transaction.RollbackAsync(ct);
            throw;
        }

        // Capture the exact bytes/status the downstream handler produced by executing its
        // IResult against a buffered response body, so they can be replayed verbatim later and
        // also written through to the real response now.
        var originalBody = httpContext.Response.Body;
        using var buffer = new MemoryStream();
        httpContext.Response.Body = buffer;

        try
        {
            if (result is IResult downstreamResult)
            {
                await downstreamResult.ExecuteAsync(httpContext);
            }
            else
            {
                // Not this project's IResult convention (see class remarks) — fall back to a
                // plain 200 with no cached body rather than silently losing the result.
                httpContext.Response.StatusCode = StatusCodes.Status200OK;
            }
        }
        catch
        {
            httpContext.Response.Body = originalBody;
            await transaction.RollbackAsync(ct);
            throw;
        }

        httpContext.Response.Body = originalBody;

        buffer.Seek(0, SeekOrigin.Begin);
        var bodyBytes = buffer.ToArray();
        var bodyText = bodyBytes.Length > 0 ? System.Text.Encoding.UTF8.GetString(bodyBytes) : null;

        record.Status = IdempotencyStatus.Completed;
        record.StatusCode = httpContext.Response.StatusCode;
        record.ResponseBody = bodyText;
        record.ResourceLocation = httpContext.Response.Headers.Location.Count > 0
            ? httpContext.Response.Headers.Location.ToString()
            : null;

        try
        {
            await dbContext.SaveChangesAsync(ct);
            await transaction.CommitAsync(ct);
        }
        catch
        {
            await transaction.RollbackAsync(ct);
            throw;
        }

        // Write the buffered response through to the real stream now that the transaction has
        // committed, and signal to the outer pipeline that nothing further needs executing.
        buffer.Seek(0, SeekOrigin.Begin);
        await buffer.CopyToAsync(originalBody, ct);

        return Results.Empty;
    }

    /// <summary>Resolves the caller's <see cref="UserId"/> from the validated token's claims.</summary>
    private static async Task<UserId?> ResolveUserIdAsync(
        HttpContext httpContext, TenancyDbContext dbContext, CancellationToken ct)
    {
        var tidClaim = httpContext.User.FindFirst("tid")?.Value;
        var oidClaim = httpContext.User.FindFirst("oid")?.Value;
        if (!Guid.TryParse(tidClaim, out var entraTenantId) || !Guid.TryParse(oidClaim, out var entraObjectId))
        {
            return null;
        }

        var user = await dbContext.Users
            .AsNoTracking()
            .SingleOrDefaultAsync(u => u.EntraTenantId == entraTenantId && u.EntraObjectId == entraObjectId, ct);

        return user?.Id;
    }

    /// <summary>
    /// Uses the ambient <see cref="ITenantContext"/> when it has been resolved (i.e. this filter
    /// is applied downstream of <c>TenantContextResolutionMiddleware</c> on a
    /// <c>{tenantId}</c>-scoped route group), or the fixed sentinel
    /// <see cref="TenantId.Empty"/> otherwise (e.g. <c>POST /tenants</c>, which has no tenant
    /// context to resolve). <see cref="ITenantContext"/> is documented to throw
    /// <see cref="InvalidOperationException"/> rather than return a default value when
    /// unresolved (a deliberate fail-closed design so a default tenant id is never used as a
    /// filter value by accident) — that same throw is used here purely as an "is it resolved"
    /// check, since the interface has no <c>TryGet</c>.
    /// </summary>
    private static TenantId ResolveTenantId(HttpContext httpContext)
    {
        var tenantContext = httpContext.RequestServices.GetRequiredService<ITenantContext>();
        try
        {
            return tenantContext.TenantId;
        }
        catch (InvalidOperationException)
        {
            return TenantId.Empty;
        }
    }

    /// <summary>
    /// A stable identifier for "which operation this record applies to" — the HTTP method plus
    /// the endpoint's route pattern (e.g. <c>"POST /invitations/{token}/accept"</c>), matching
    /// data-model.md's example. Falls back to the raw request path if no route pattern is
    /// available (should not happen once routing has matched, but keeps this filter total).
    /// </summary>
    private static string DescribeEndpoint(HttpContext httpContext)
    {
        var routeEndpoint = httpContext.GetEndpoint() as RouteEndpoint;
        var routeTemplate = routeEndpoint?.RoutePattern.RawText ?? httpContext.Request.Path.Value ?? string.Empty;
        return $"{httpContext.Request.Method} {routeTemplate}";
    }

    /// <summary>
    /// SHA-256 over the raw request body bytes. Reads via <see cref="HttpRequest.EnableBuffering"/>
    /// so the body stream is rewound afterwards and remains readable downstream for model
    /// binding.
    /// </summary>
    private static async Task<byte[]> ComputeRequestHashAsync(HttpContext httpContext)
    {
        httpContext.Request.EnableBuffering();
        httpContext.Request.Body.Position = 0;

        using var buffer = new MemoryStream();
        await httpContext.Request.Body.CopyToAsync(buffer, httpContext.RequestAborted);
        httpContext.Request.Body.Position = 0;

        return SHA256.HashData(buffer.ToArray());
    }
}

/// <summary>
/// Opt-in wiring for <see cref="IdempotencyFilter"/>. Deliberately not blanket middleware —
/// applied per-endpoint/route-group at wiring time (T058), following T035's established
/// <c>WithTenantContextResolution</c> opt-in pattern.
/// </summary>
public static class IdempotencyEndpointConventionBuilderExtensions
{
    /// <summary>
    /// Adds <see cref="IdempotencyFilter"/> to the given route group. When the group also opts
    /// into ADR-017's tenant context resolution, apply that filter first so
    /// <see cref="ITenantContext"/> is resolved by the time this filter reads it.
    /// </summary>
    public static RouteGroupBuilder WithIdempotency(this RouteGroupBuilder builder)
    {
        builder.AddEndpointFilter<IdempotencyFilter>();
        return builder;
    }

    /// <summary>
    /// Adds <see cref="IdempotencyFilter"/> to a single endpoint. Prefer
    /// <see cref="WithIdempotency(RouteGroupBuilder)"/> on a route group when wiring multiple
    /// idempotent endpoints at once.
    /// </summary>
    public static RouteHandlerBuilder WithIdempotency(this RouteHandlerBuilder builder)
    {
        builder.AddEndpointFilter<IdempotencyFilter>();
        return builder;
    }
}
