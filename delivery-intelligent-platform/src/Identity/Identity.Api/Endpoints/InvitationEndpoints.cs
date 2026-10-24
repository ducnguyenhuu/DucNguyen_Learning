using Identity.Api.Authorization;
using Identity.Api.Idempotency;
using Identity.Api.Middleware;
using Identity.Application.Invitations;
using Identity.Application.Users;
using Identity.Domain.Abstractions;
using Identity.Domain.Invitations;

namespace Identity.Api.Endpoints;

/// <summary>
/// T078 — the invitation endpoints, wiring T071-T073's use cases (InviteMember, AcceptInvitation,
/// ListInvitations, RevokeInvitation) onto HTTP, mirroring <see cref="MemberEndpoints"/> in
/// structure and conventions.
/// </summary>
/// <remarks>
/// <para>
/// <b>Invite/list/revoke are administrator-only</b> (FR-011/FR-014): the group opts into
/// <c>RequireMembership()</c> and each route into <c>RequireAdministrator()</c>, in that order.
/// </para>
/// <para>
/// <b><c>Location</c> header on <c>POST /invitations</c>:</b> the contract's <c>Location</c> header
/// schema is a bare <c>{ type: string, format: uri }</c> with no further specification, and there
/// is no <c>GET /invitations/{id}</c> single-resource route in <c>contracts/openapi.yaml</c> to
/// point at. This endpoint therefore points <c>Location</c> at the list route
/// (<c>GET /invitations</c>) — the closest existing resource that contains the created invitation.
/// </para>
/// <para>
/// <b><c>POST /invitations/{token}/accept</c> does not require membership</b> — the caller becomes
/// a member only by accepting — so it gets just <c>RequireAuthorization()</c>.
/// <see cref="AcceptInvitation"/> calls <see cref="EnsureUserProvisioned"/> internally.
/// </para>
/// </remarks>
public static class InvitationEndpoints
{
    public static IEndpointRouteBuilder MapInvitationEndpoints(this IEndpointRouteBuilder app)
    {
        // Member-only: opts into the membership resolution filter, same group shape as
        // MemberEndpoints.members.
        var invitations = app.MapGroup("/invitations")
            .RequireAuthorization()
            .RequireMembership();

        invitations.MapPost("/", CreateInvitationAsync)
            .RequireAdministrator()
            .WithIdempotency();

        invitations.MapGet("/", ListInvitationsAsync)
            .RequireAdministrator();

        invitations.MapDelete("/{invitationId}", RevokeInvitationAsync)
            .RequireAdministrator();

        // Not member-only — the caller has no membership until this succeeds.
        app.MapPost("/invitations/{token}/accept", AcceptInvitationAsync)
            .RequireAuthorization();

        return app;
    }

    private static async Task<IResult> CreateInvitationAsync(
        HttpContext httpContext,
        CreateInvitationRequest request,
        InviteMember inviteMember,
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

        EmailAddress email;
        Role role;
        try
        {
            email = new EmailAddress(request.Email);
            role = Enum.Parse<Role>(request.Role, ignoreCase: true);
        }
        catch (Exception ex) when (ex is FormatException or ArgumentException)
        {
            return Results.Problem(
                title: "Invalid invitation",
                detail: ex.Message,
                statusCode: StatusCodes.Status400BadRequest);
        }

        InviteMemberResult result;
        try
        {
            result = await inviteMember.ExecuteAsync(email, role, caller.Id, ct);
        }
        catch (ConflictException ex)
        {
            return Results.Problem(
                title: "Invitation conflict",
                detail: ex.Message,
                statusCode: StatusCodes.Status409Conflict);
        }
        catch (DomainException ex)
        {
            return Results.Problem(
                title: "Invalid invitation",
                detail: ex.Message,
                statusCode: StatusCodes.Status400BadRequest);
        }

        var dto = InvitationDto.FromDomain(result.Invitation, result.RawToken);

        // Location points at the list route: there is no single-resource GET /invitations/{id}
        // route in the contract (see this class's remarks).
        return Results.Created("/invitations", dto);
    }

    private static async Task<IResult> ListInvitationsAsync(
        HttpContext httpContext,
        ListInvitations listInvitations,
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

        var invitations = await listInvitations.ExecuteAsync(caller.Id, ct);
        var dtos = invitations.Select(ListedInvitationDto.FromResult).ToList();

        return Results.Ok(dtos);
    }

    private static async Task<IResult> RevokeInvitationAsync(
        HttpContext httpContext,
        Guid invitationId,
        RevokeInvitation revokeInvitation,
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

        var result = await revokeInvitation.ExecuteAsync(new InvitationId(invitationId), caller.Id, ct);

        return result.Kind switch
        {
            RevokeInvitationResultKind.Success => Results.NoContent(),
            RevokeInvitationResultKind.NotFound => Results.NotFound(),
            RevokeInvitationResultKind.Conflict => Results.Problem(
                title: "Invitation conflict",
                detail: "The invitation is no longer pending.",
                statusCode: StatusCodes.Status409Conflict),
            _ => Results.Problem(statusCode: StatusCodes.Status500InternalServerError),
        };
    }

    private static async Task<IResult> AcceptInvitationAsync(
        HttpContext httpContext,
        string token,
        AcceptInvitation acceptInvitation,
        CancellationToken ct)
    {
        var tidClaim = httpContext.User.FindFirst("tid")?.Value;
        var oidClaim = httpContext.User.FindFirst("oid")?.Value;
        if (!Guid.TryParse(tidClaim, out var entraTenantId) || !Guid.TryParse(oidClaim, out var entraObjectId))
        {
            return Results.Problem(
                title: "Caller could not be resolved",
                detail: "No usable identity claims were present on the token.",
                statusCode: StatusCodes.Status401Unauthorized);
        }

        var emailClaim =
            httpContext.User.FindFirst("email")?.Value ??
            httpContext.User.FindFirst("preferred_username")?.Value ??
            httpContext.User.FindFirst("upn")?.Value;

        var callerEmail = new EmailAddress(
            string.IsNullOrWhiteSpace(emailClaim) ? $"{entraObjectId}@unresolved.invalid" : emailClaim);

        var result = await acceptInvitation.ExecuteAsync(token, entraTenantId, entraObjectId, callerEmail, ct);

        switch (result.Kind)
        {
            case AcceptInvitationResultKind.Success:
                // Member shape per openapi.yaml. displayName cannot be populated — Domain.Users.User
                // has no such property (same honest omission T076's ListedMember documents).
                var membership = result.Membership!;
                var dto = new AcceptedMemberDto(
                    membership.UserId.Value,
                    callerEmail.Value,
                    DisplayName: string.Empty,
                    membership.Role.ToString(),
                    membership.Status.ToString());
                return Results.Ok(dto);

            case AcceptInvitationResultKind.NotFound:
            case AcceptInvitationResultKind.NotAcceptable:
                // Both collapse to the same 404, per T065's indistinguishability requirement.
                return Results.NotFound();

            case AcceptInvitationResultKind.WrongIdentity:
                return Results.Problem(
                    title: "Wrong identity",
                    detail: "The authenticated caller does not match the invited address.",
                    statusCode: StatusCodes.Status403Forbidden);

            case AcceptInvitationResultKind.AlreadyMember:
                return Results.Problem(
                    title: "Already a member",
                    detail: "The authenticated caller is already a member of the organization.",
                    statusCode: StatusCodes.Status409Conflict);

            default:
                return Results.Problem(statusCode: StatusCodes.Status500InternalServerError);
        }
    }

    /// <summary>
    /// Same JIT-provisioning shape as <c>MemberEndpoints.ProvisionCallerAsync</c> — kept as a
    /// private duplicate here rather than a shared helper, the precedent both files follow.
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

/// <summary>Request body for <c>POST /invitations</c>, per openapi.yaml.</summary>
public sealed record CreateInvitationRequest(string Email, string Role);

/// <summary>
/// The <c>Invitation</c> response schema (<c>allOf</c> base fields + <c>token</c>) per
/// openapi.yaml, for <c>POST /invitations</c>'s 201 response.
/// </summary>
public sealed record InvitationDto(
    Guid Id,
    string Email,
    string Role,
    string Status,
    DateTimeOffset ExpiresAtUtc,
    string Token)
{
    public static InvitationDto FromDomain(Invitation invitation, string rawToken) =>
        new(
            invitation.Id.Value,
            invitation.Email.Value,
            invitation.Role.ToString(),
            invitation.Status.ToString(),
            invitation.ExpiresAtUtc,
            rawToken);
}

/// <summary>The <c>Invitation</c> response schema per openapi.yaml, for the list endpoint (no
/// <c>token</c> field — that is only ever returned once, at creation).</summary>
public sealed record ListedInvitationDto(
    Guid Id,
    string Email,
    string Role,
    string Status,
    DateTimeOffset ExpiresAtUtc)
{
    public static ListedInvitationDto FromResult(ListedInvitation invitation) =>
        new(
            invitation.Id.Value,
            invitation.Email.Value,
            invitation.Role.ToString(),
            invitation.Status.ToString(),
            invitation.ExpiresAtUtc);
}

/// <summary>The <c>Member</c> response schema per openapi.yaml, for
/// <c>POST /invitations/{token}/accept</c>'s 200 response. <see cref="DisplayName"/> is always
/// empty — <see cref="Domain.Users.User"/> has no display-name property to source it from (same
/// honest omission T076's <c>ListedMember</c> documents).</summary>
public sealed record AcceptedMemberDto(
    Guid UserId,
    string Email,
    string DisplayName,
    string Role,
    string Status);
