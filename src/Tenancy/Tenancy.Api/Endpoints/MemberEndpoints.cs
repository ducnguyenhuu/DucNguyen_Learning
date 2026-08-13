using Tenancy.Api.ETags;
using Tenancy.Application.Abstractions;
using Tenancy.Api.Middleware;
using Tenancy.Application.Members;
using Tenancy.Application.Users;
using Tenancy.Domain.Abstractions;

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

        scopedMembers.MapGet("/", ListMembersAsync);

        scopedMembers.MapDelete("/{userId}", RemoveMemberAsync);

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
