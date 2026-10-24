using Microsoft.EntityFrameworkCore;
using Identity.Api.Authorization;
using Identity.Api.ETags;
using Identity.Application.Abstractions;
using Identity.Api.Middleware;
using Identity.Application.Members;
using Identity.Application.Users;
using Identity.Domain.Abstractions;
using Identity.Domain.Memberships;
using Identity.Infrastructure.Persistence;

namespace Identity.Api.Endpoints;

/// <summary>
/// The member endpoints: <c>GET /me</c>, <c>POST /members/bootstrap</c> (ADR-025), and the
/// administrator-only <c>/members</c> list/remove/role-change routes wiring
/// <see cref="ListMembers"/>, <see cref="RemoveMember"/> and <see cref="ChangeMemberRole"/> onto
/// HTTP. <see cref="InvitationEndpoints"/> follows the same structure and conventions.
/// </summary>
/// <remarks>
/// <para>
/// <b>Administrator-only routes</b> (FR-014): the <c>/members</c> group opts into
/// <c>RequireMembership()</c> and each route into <c>RequireAdministrator()</c>, in that order.
/// <c>GET /me</c> and <c>POST /members/bootstrap</c> sit outside that group, because their caller
/// may not be a member yet.
/// </para>
/// <para>
/// <b><c>displayName</c> not populated</b> on <see cref="MemberDto"/>: <see cref="ListedMember"/>
/// (T076) already carries the same honest omission — <see cref="Domain.Users.User"/> has no
/// display-name property anywhere in the domain model today. Carried through as an empty string
/// rather than invented.
/// </para>
/// <para>
/// <b>412 vs 428 vs 409 on <c>DELETE</c>, the same pattern as <c>PATCH /members/{userId}</c>:</b>
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
/// <c>409 Conflict</c> here. A stale caller was already caught above as 412; anything still
/// reaching <see cref="RemoveMember"/>'s conflict result is either the last-administrator
/// invariant or a race that slipped past the pre-check — and <c>contracts/openapi.yaml</c>'s own
/// text for this route ("Concurrency race, or would leave the organization with no
/// Administrator") treats both as one 409, not two separate codes.
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
        // Not member-only: any authenticated caller may ask who they are, and the first caller
        // ever needs to reach bootstrap before any membership exists.
        app.MapGet("/me", GetMeAsync)
            .RequireAuthorization();

        app.MapPost("/members/bootstrap", BootstrapAsync)
            .RequireAuthorization();

        // Member-only: opts into the membership resolution filter, same group shape as
        // InvitationEndpoints.invitations.
        var members = app.MapGroup("/members")
            .RequireAuthorization()
            .RequireMembership();

        members.MapGet("/", ListMembersAsync)
            .RequireAdministrator();

        members.MapDelete("/{userId}", RemoveMemberAsync)
            .RequireAdministrator();

        members.MapPatch("/{userId}", PatchMemberRoleAsync)
            .RequireAdministrator();

        return app;
    }

    /// <summary>
    /// <c>GET /me</c> (ADR-025) — the caller's own user id, email and role. <c>role</c> is
    /// <c>null</c> when the caller is not a member, which is a normal answer, not an error.
    /// </summary>
    private static async Task<IResult> GetMeAsync(
        HttpContext httpContext,
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

        var membership = await membershipRepository.GetActiveMembershipForUserAsync(caller.Id, ct);

        return Results.Ok(new MeDto(caller.Id.Value, caller.Email.Value, membership?.Role.ToString()));
    }

    /// <summary>
    /// <c>POST /members/bootstrap</c> (ADR-025) — makes the caller the first Administrator while
    /// the organization has no members: <c>201</c>, or <c>409</c> once anyone is a member. Only a
    /// delegated user token may call it (<c>403</c> otherwise): an application identity must never
    /// become the first administrator.
    /// </summary>
    private static async Task<IResult> BootstrapAsync(
        HttpContext httpContext,
        EnsureUserProvisioned ensureUserProvisioned,
        BootstrapAdministrator bootstrapAdministrator,
        CancellationToken ct)
    {
        if (!CallerAuthorizationPolicy.IsDelegatedUser(httpContext.User))
        {
            return Results.Problem(
                title: "Delegated user required",
                detail: "Only a signed-in user can bootstrap the first administrator.",
                statusCode: StatusCodes.Status403Forbidden);
        }

        var caller = await ProvisionCallerAsync(httpContext, ensureUserProvisioned, ct);
        if (caller is null)
        {
            return Results.Problem(
                title: "Caller could not be resolved",
                detail: "No usable identity claims were present on the token.",
                statusCode: StatusCodes.Status401Unauthorized);
        }

        var result = await bootstrapAdministrator.ExecuteAsync(caller.Id, ct);
        if (result.Kind == BootstrapAdministratorResultKind.Conflict)
        {
            return Results.Problem(
                title: "Already bootstrapped",
                detail: "The organization already has members; new members join by invitation.",
                statusCode: StatusCodes.Status409Conflict);
        }

        var membership = result.Membership!;
        var dto = new MemberDto(
            caller.Id.Value,
            caller.Email.Value,
            DisplayName: string.Empty,
            membership.Role.ToString(),
            membership.Status.ToString());

        return Results.Created($"/members/{caller.Id.Value}", dto)
            .WithHeader("ETag", RowVersionETag.ToETag(membership.RowVersion));
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
                detail: "Removing this member would leave the organization with no Administrator, " +
                    "or the membership was concurrently modified.",
                statusCode: StatusCodes.Status409Conflict),
            _ => Results.Problem(statusCode: StatusCodes.Status500InternalServerError),
        };
    }

    /// <summary>
    /// <c>PATCH /members/{userId}</c> (T087) — changes the target member's role, wiring T086's
    /// <see cref="ChangeMemberRole"/> use case, with this 428/400/412/409 <c>If-Match</c>
    /// disambiguation shape:
    /// </summary>
    /// <remarks>
    /// <list type="bullet">
    /// <item>Missing <c>If-Match</c>: <c>428</c>.</item>
    /// <item>Malformed <c>If-Match</c>: <c>400</c>.</item>
    /// <item>Malformed/unknown <c>role</c> in the request body: <c>400</c>.</item>
    /// <item>No active membership for <c>userId</c>: <c>404</c>, checked
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
    /// the decoded <c>If-Match</c> bytes (ADR-020) before calling <see cref="ChangeMemberRole.ExecuteAsync"/>. If that save still throws
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
        IdentityDbContext dbContext,
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
        // (EF's concurrency-check baseline) before ChangeMemberRole mutates and saves it (ADR-020).
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
                detail: "Changing this member's role would leave the organization with no Administrator, " +
                    "or the membership was concurrently modified.",
                statusCode: StatusCodes.Status409Conflict),
            _ => Results.Problem(statusCode: StatusCodes.Status500InternalServerError),
        };
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

    /// <summary>
    /// JIT-provisions the caller from the validated token's <c>(tid, oid)</c> claims, with a
    /// best-effort email claim lookup. Test tokens (Tier 1 <c>TestAuthHandler</c> and Tier 2
    /// <c>SignedTokenHarness</c>) carry no email claim at all, so a deterministic placeholder is
    /// synthesized from the caller's <c>oid</c> when none is present — display/invitation-matching
    /// only (research.md R2), never an authorization input, so this placeholder is harmless.
    /// <c>InvitationEndpoints.ProvisionCallerAsync</c> is a private duplicate of this, the
    /// precedent both files follow.
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

/// <summary>The <c>Member</c> response schema per openapi.yaml, for <c>GET /members</c>. <see cref="DisplayName"/> is always empty —
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

/// <summary>Request body for <c>PATCH /members/{userId}</c>, per openapi.yaml.</summary>
public sealed record ChangeMemberRoleRequest(string Role);

/// <summary>The <c>Me</c> response schema for <c>GET /me</c> (ADR-025). <see cref="Role"/> is
/// <c>null</c> when the caller has no active membership.</summary>
public sealed record MeDto(Guid UserId, string Email, string? Role);
