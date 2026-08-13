using Microsoft.EntityFrameworkCore;
using Tenancy.Api.Authorization;
using Tenancy.Api.ETags;
using Tenancy.Application.Abstractions;
using Tenancy.Api.Middleware;
using Tenancy.Application.Members;
using Tenancy.Application.Users;
using Tenancy.Domain.Abstractions;
using Tenancy.Domain.Memberships;
using Tenancy.Infrastructure.Persistence;

namespace Tenancy.Api.Endpoints;

/// <summary>
/// T079 — the two <c>/tenants/{tenantId}/members</c> endpoints, wiring T076's <see cref="ListMembers"/>
/// and <see cref="RemoveMember"/> use cases onto HTTP, mirroring T058's <see cref="TenantEndpoints"/>
/// and T078's <see cref="InvitationEndpoints"/> in structure and conventions.
/// </summary>
/// <remarks>
/// <para>
/// <b>No administrator-only check anywhere in this file:</b> FR-014 says list/remove are
/// administrator-only, but role-based authorization is Phase 5's job — same deliberate phasing as
/// every prior endpoint task.
/// </para>
/// <para>
/// <b><c>displayName</c> not populated</b> on <see cref="MemberDto"/>: <see cref="ListedMember"/>
/// (T076) already carries the same honest omission — <see cref="Domain.Users.User"/> has no
/// display-name property anywhere in the domain model today. Carried through as an empty string
/// rather than invented.
/// </para>
/// <para>
/// <b>412 vs 428 vs 409 on <c>DELETE</c>, following T058's established pattern for
/// <c>PATCH /tenants/{tenantId}</c>:</b>
/// </para>
/// <list type="bullet">
/// <item>Missing <c>If-Match</c> entirely: <c>428 Precondition Required</c> — the caller supplied
/// no version to condition the removal on at all.</item>
/// <item>Malformed <c>If-Match</c> (not a well-formed quoted base64 ETag,
/// <see cref="RowVersionETag.FromIfMatch"/> throws <see cref="FormatException"/>): <c>400 Bad
/// Request</c>.</item>
/// <item>
/// Decode succeeds, so a fresh, pre-removal read of the target <see cref="Domain.Memberships.Membership"/>'s
/// current <c>RowVersion</c> is compared against the decoded bytes <b>before</b> calling
/// <see cref="RemoveMember.ExecuteAsync"/> at all — exactly T058's "fresh read immediately before
/// the write" signal. If they already don't match, the caller's view was stale before this
/// request even tried to remove anything: <c>412 Precondition Failed</c>.
/// </item>
/// <item>
/// If they matched at read time, but <see cref="RemoveMember.ExecuteAsync"/> still comes back
/// <see cref="RemoveMemberResultKind.Conflict"/> — either <see cref="IMembershipRepository.RemoveMembershipAsync"/>'s
/// (T075) last-administrator invariant refused the removal, or a genuine, narrower race landed a
/// second write between this endpoint's fresh read and that call's own save — both collapse to
/// <c>409 Conflict</c> here. Unlike <c>PATCH /tenants/{tenantId}</c>'s 412-vs-409 split (which
/// distinguishes a <b>stale caller</b> from a <b>genuine save-time race</b>), a stale caller was
/// already caught above as 412; anything still reaching <see cref="RemoveMember"/>'s conflict
/// result is either the last-administrator invariant or a race that slipped past the pre-check —
/// and <c>contracts/openapi.yaml</c>'s own text for this route ("Concurrency race, or would leave
/// the tenant with no Administrator") treats both as one 409, not two separate codes.
/// </item>
/// <item>Success: <c>204 No Content</c>.</item>
/// <item><see cref="RemoveMember.ExecuteAsync"/> reporting
/// <see cref="RemoveMemberResultKind.NotFound"/> (unknown/inactive <c>userId</c>): <c>404 Not
/// Found</c> — checked before the If-Match precondition logic even runs, since there is nothing to
/// condition a removal on when the target does not exist as an active member.</item>
/// </list>
/// </remarks>
public static class MemberEndpoints
{
    public static IEndpointRouteBuilder MapMemberEndpoints(this IEndpointRouteBuilder app)
    {
        // Tenant-scoped: opts into T035's resolution filter, same group shape as
        // TenantEndpoints.scopedTenant / InvitationEndpoints.scopedInvitations.
        var scopedMembers = app.MapGroup("/tenants/{tenantId}/members")
            .RequireAuthorization()
            .WithTenantContextResolution();

        scopedMembers.MapGet("/", ListMembersAsync)
            .RequireTenantAdministrator();

        scopedMembers.MapDelete("/{userId}", RemoveMemberAsync)
            .RequireTenantAdministrator();

        scopedMembers.MapPatch("/{userId}", PatchMemberRoleAsync)
            .RequireTenantAdministrator();

        return app;
    }

    private static async Task<IResult> ListMembersAsync(
        HttpContext httpContext,
        ListMembers listMembers,
        EnsureUserProvisioned ensureUserProvisioned,
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

        var members = await listMembers.ExecuteAsync(caller.Id, ct);
        var dtos = members.Select(MemberDto.FromResult).ToList();

        return Results.Ok(dtos);
    }

    private static async Task<IResult> RemoveMemberAsync(
        HttpContext httpContext,
        Guid userId,
        RemoveMember removeMember,
        EnsureUserProvisioned ensureUserProvisioned,
        IMembershipRepository membershipRepository,
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

        var targetUserId = new UserId(userId);

        if (!httpContext.Request.Headers.TryGetValue("If-Match", out var ifMatchValues) ||
            string.IsNullOrWhiteSpace(ifMatchValues.ToString()))
        {
            return Results.Problem(
                title: "If-Match header required",
                detail: "This operation requires an If-Match header naming the version being removed.",
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

        // Fresh, pre-removal read of the target membership's actual current RowVersion — the "did
        // the caller's If-Match already not match at request start" signal the 412-vs-409
        // distinction (see this class's remarks) depends on. RemoveMember does its own,
        // independent lookup below; this one is purely for the precondition check.
        var currentMembership = await membershipRepository.GetActiveMembershipForUserAsync(targetUserId, ct);
        if (currentMembership is null)
        {
            return Results.NotFound();
        }

        if (!decodedIfMatch.AsSpan().SequenceEqual(currentMembership.RowVersion))
        {
            // Already stale relative to what a fresh read shows, before any removal was attempted.
            return Results.Problem(
                title: "Precondition failed",
                detail: "The supplied If-Match value is stale.",
                statusCode: StatusCodes.Status412PreconditionFailed);
        }

        var result = await removeMember.ExecuteAsync(targetUserId, caller.Id, ct);

        return result.Kind switch
        {
            RemoveMemberResultKind.Success => Results.NoContent(),
            RemoveMemberResultKind.NotFound => Results.NotFound(),
            RemoveMemberResultKind.Conflict => Results.Problem(
                title: "Member conflict",
                detail: "Removing this member would leave the tenant with no Administrator, " +
                    "or the membership was concurrently modified.",
                statusCode: StatusCodes.Status409Conflict),
            _ => Results.Problem(statusCode: StatusCodes.Status500InternalServerError),
        };
    }

    /// <summary>
    /// <c>PATCH /tenants/{tenantId}/members/{userId}</c> (T087) — changes the target member's
    /// role, wiring T086's <see cref="ChangeMemberRole"/> use case. Mirrors
    /// <c>TenantEndpoints.PatchTenantAsync</c>'s (T058) exact 428/400/412/409 <c>If-Match</c>
    /// disambiguation shape:
    /// </summary>
    /// <remarks>
    /// <list type="bullet">
    /// <item>Missing <c>If-Match</c>: <c>428</c>.</item>
    /// <item>Malformed <c>If-Match</c>: <c>400</c>.</item>
    /// <item>Malformed/unknown <c>role</c> in the request body: <c>400</c>.</item>
    /// <item>No active membership for <c>userId</c> in the current tenant: <c>404</c>, checked
    /// before the precondition logic (nothing to condition a role change on when the target
    /// doesn't exist).</item>
    /// <item>
    /// A fresh, pre-update read of the target membership's current <c>RowVersion</c>, compared
    /// against the decoded <c>If-Match</c> bytes before attempting the change at all: mismatch
    /// here means the caller's view was already stale before this request tried to write —
    /// <c>412</c>.
    /// </item>
    /// <item>
    /// If they matched at read time, the tracked entity's original <c>RowVersion</c> is pinned to
    /// the decoded <c>If-Match</c> bytes (mirroring <c>RenameWithOriginalRowVersionAsync</c>)
    /// before calling <see cref="ChangeMemberRole.ExecuteAsync"/>. If that save still throws
    /// <see cref="DbUpdateConcurrencyException"/>, a second, unrelated write landed between the
    /// fresh read and the update — a genuine race at save time: <c>409</c>.
    /// </item>
    /// <item><see cref="ChangeMemberRoleResultKind.Conflict"/> (last-administrator invariant):
    /// <c>409</c> — per the contract's own text, collapsed with the save-time race case, same as
    /// T079's <c>DELETE</c> precedent.</item>
    /// <item><see cref="ChangeMemberRoleResultKind.NotFound"/>: <c>404</c>.</item>
    /// <item>Success: <c>200</c> with the updated <see cref="MemberDto"/> shape and a fresh
    /// <c>ETag</c>.</item>
    /// </list>
    /// </remarks>
    private static async Task<IResult> PatchMemberRoleAsync(
        HttpContext httpContext,
        Guid userId,
        ChangeMemberRoleRequest request,
        ChangeMemberRole changeMemberRole,
        EnsureUserProvisioned ensureUserProvisioned,
        IMembershipRepository membershipRepository,
        TenancyDbContext dbContext,
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

        if (!Enum.TryParse<Role>(request.Role, ignoreCase: true, out var newRole) ||
            !Enum.IsDefined(newRole))
        {
            return Results.Problem(
                title: "Invalid role",
                detail: $"'{request.Role}' is not a recognized role.",
                statusCode: StatusCodes.Status400BadRequest);
        }

        var targetUserId = new UserId(userId);

        // Existence check first, ahead of the If-Match precondition logic: per T083's own test
        // (Patch_MemberRole_ForUserWithNoActiveMembership_ReturnsNotFound — no If-Match header
        // supplied at all, still expects 404, not 428), there is nothing to condition a role
        // change on when the target does not exist as an active member at all.
        var currentMembership = await membershipRepository.GetActiveMembershipForUserAsync(targetUserId, ct);
        if (currentMembership is null)
        {
            return Results.NotFound();
        }

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

        if (!decodedIfMatch.AsSpan().SequenceEqual(currentMembership.RowVersion))
        {
            // Already stale relative to what a fresh read shows, before any write was attempted.
            return Results.Problem(
                title: "Precondition failed",
                detail: "The supplied If-Match value is stale.",
                statusCode: StatusCodes.Status412PreconditionFailed);
        }

        // Pin the tracked entity's original RowVersion to the caller's decoded If-Match bytes
        // (EF's concurrency-check baseline) before ChangeMemberRole mutates and saves it, mirroring
        // TenantEndpoints.RenameWithOriginalRowVersionAsync (T058).
        var tracked = await dbContext.Memberships
            .SingleOrDefaultAsync(m => m.UserId == targetUserId && m.Status == MembershipStatus.Active, ct);
        if (tracked is null)
        {
            return Results.NotFound();
        }

        var trackedEntry = dbContext.Entry(tracked);
        trackedEntry.Property(nameof(Membership.RowVersion)).OriginalValue = decodedIfMatch;

        // Force a real UPDATE (and thus the optimistic-concurrency check against the pinned
        // OriginalValue above) even when the caller's requested role happens to equal the
        // membership's current role: without this, EF's change tracker sees zero modified scalar
        // properties for a same-value "change" and skips SaveChanges' UPDATE entirely — silently
        // "succeeding" without the concurrency check ever running against the database at all.
        // T084's concurrent-race test exercises exactly this (one racing caller requests the
        // member's already-current role), so this can't be left to chance.
        trackedEntry.State = EntityState.Modified;

        ChangeMemberRoleResult result;
        try
        {
            result = await changeMemberRole.ExecuteAsync(targetUserId, newRole, caller.Id, ct);
        }
        catch (DbUpdateConcurrencyException)
        {
            // The If-Match value matched a fresh read moments ago, yet the save still lost the
            // optimistic-concurrency check: someone else's write landed in between. A genuine
            // race at save time, not a stale caller.
            return Results.Problem(
                title: "Concurrency conflict",
                detail: "The membership was modified by another request while this update was in flight.",
                statusCode: StatusCodes.Status409Conflict);
        }

        if (result.Kind == ChangeMemberRoleResultKind.Success)
        {
            var targetUser = await dbContext.Users.SingleOrDefaultAsync(u => u.Id == targetUserId, ct);
            var dto = new MemberDto(
                targetUserId.Value,
                targetUser?.Email.Value ?? string.Empty,
                DisplayName: string.Empty,
                result.Membership!.Role.ToString(),
                result.Membership!.Status.ToString());

            return Results.Ok(dto).WithHeader("ETag", RowVersionETag.ToETag(result.Membership!.RowVersion));
        }

        return result.Kind switch
        {
            ChangeMemberRoleResultKind.NotFound => Results.NotFound(),
            ChangeMemberRoleResultKind.Conflict => Results.Problem(
                title: "Member conflict",
                detail: "Changing this member's role would leave the tenant with no Administrator, " +
                    "or the membership was concurrently modified.",
                statusCode: StatusCodes.Status409Conflict),
            _ => Results.Problem(statusCode: StatusCodes.Status500InternalServerError),
        };
    }

    private static IResult WithHeader(this IResult result, string name, string value) =>
        new HeaderDecoratedResult(result, name, value);

    /// <summary>
    /// Wraps an inner <see cref="IResult"/> to add one response header when executed — a private
    /// duplicate of <c>TenantEndpoints.HeaderDecoratedResult</c> (T058), same precedent this file
    /// already follows for <c>ProvisionCallerAsync</c>.
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

    /// <summary>
    /// Same JIT-provisioning shape as <c>TenantEndpoints.ProvisionCallerAsync</c> (T058) and
    /// <c>InvitationEndpoints.ProvisionCallerAsync</c> (T078) — kept as a private duplicate here
    /// rather than a shared helper, following the same precedent those two files already set.
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
}

/// <summary>The <c>Member</c> response schema per openapi.yaml, for <c>GET
/// /tenants/{tenantId}/members</c>. <see cref="DisplayName"/> is always empty —
/// <see cref="Domain.Users.User"/> has no display-name property to source it from (same honest
/// omission T076's <see cref="ListedMember"/> documents).</summary>
public sealed record MemberDto(
    Guid UserId,
    string Email,
    string DisplayName,
    string Role,
    string Status)
{
    public static MemberDto FromResult(ListedMember member) =>
        new(
            member.UserId.Value,
            member.Email?.Value ?? string.Empty,
            DisplayName: string.Empty,
            member.Role.ToString(),
            member.Status.ToString());
}

/// <summary>Request body for <c>PATCH /tenants/{tenantId}/members/{userId}</c>, per openapi.yaml.</summary>
public sealed record ChangeMemberRoleRequest(string Role);
