using Microsoft.AspNetCore.Authorization;
using Microsoft.Extensions.Logging;
using Identity.Application.Abstractions;
using Identity.Domain.Abstractions;
using Identity.Domain.Auditing;

namespace Identity.Api.Authorization;

/// <summary>
/// Evaluates <see cref="AdministratorOnlyRequirement"/> against <see cref="ICallerContext.Role"/>
/// — the role resolved from the caller's real, active <c>Membership</c> row (see
/// <c>MembershipResolutionFilter</c>) — never against any claim on <c>HttpContext.User</c>.
/// Reading a token claim here would defeat the point: a claim is the caller's own assertion,
/// whereas the resolved membership is the source of truth this handler must check instead.
/// </summary>
/// <remarks>
/// <para>
/// <b>Ordering / fail-closed behavior:</b> <see cref="ICallerContext"/> throws
/// <see cref="InvalidOperationException"/> if read before it has been resolved for the current
/// request (see <c>HttpContextCallerContext</c>). This handler makes <b>no attempt</b> to catch
/// that and does <b>not</b> guard against it — it lets the exception propagate.
/// </para>
/// <para>
/// This is a deliberate choice, not an oversight: ASP.NET Core's own pipeline ordering does
/// <b>not</b> guarantee membership resolution has already happened by the time a policy using
/// this handler is evaluated. <c>MembershipResolutionFilter</c> is an
/// <see cref="Microsoft.AspNetCore.Http.IEndpointFilter"/>, and endpoint filters run as part of
/// endpoint invocation — <i>after</i> <c>UseAuthorization()</c>'s middleware has already run. So a
/// policy applied the conventional way (e.g. via an <c>[Authorize(Policy = "Administrator")]</c>
/// route metadata attribute, evaluated by <c>AuthorizationMiddleware</c>) would run <b>before</b>
/// that filter ever populates <see cref="ICallerContext"/>, and this handler would always observe
/// it unresolved.
/// </para>
/// <para>
/// Given that, whichever endpoint applies this policy is responsible for ensuring it is
/// evaluated only after membership resolution — <c>RequireAdministratorFilter</c> does this by
/// invoking <c>IAuthorizationService.AuthorizeAsync</c> explicitly from an endpoint filter chained
/// after <c>MembershipResolutionFilter</c>. This handler only decides what happens if that
/// responsibility is ever dropped: letting <see cref="ICallerContext"/>'s exception propagate
/// turns an unresolved caller into an unhandled exception, which <c>ProblemDetailsHandler</c>
/// turns into a fail-closed 500 — never into a silent "succeeds" or "fails open" default. That is
/// the only acceptable behavior for a security check with a broken precondition: crash loud,
/// don't guess.
/// </para>
/// </remarks>
public sealed class AdministratorOnlyAuthorizationHandler
    : AuthorizationHandler<AdministratorOnlyRequirement>
{
    private readonly ICallerContext _callerContext;
    private readonly IAuditWriter _auditWriter;
    private readonly IClock _clock;
    private readonly ILogger<AdministratorOnlyAuthorizationHandler> _logger;

    public AdministratorOnlyAuthorizationHandler(
        ICallerContext callerContext,
        IAuditWriter auditWriter,
        IClock clock,
        ILogger<AdministratorOnlyAuthorizationHandler> logger)
    {
        _callerContext = callerContext;
        _auditWriter = auditWriter;
        _clock = clock;
        _logger = logger;
    }

    protected override async Task HandleRequirementAsync(
        AuthorizationHandlerContext context,
        AdministratorOnlyRequirement requirement)
    {
        if (_callerContext.Role == Role.Administrator)
        {
            context.Succeed(requirement);
            return;
        }

        // This is the only place in the request pipeline that knows *why* the caller was refused
        // (their actual, membership-resolved role) — the calling filter (RequireAdministratorFilter)
        // only ever sees a bare AuthorizationResult.Succeeded == false, with no role detail to
        // log. Logging here, not there, keeps the log entry as close as possible to the actual
        // decision. Only ids/role are logged — no email or token.
        _logger.LogWarning(
            "Authorization refused: user {UserId}, required role {RequiredRole}, actual role {ActualRole}",
            _callerContext.UserId,
            Role.Administrator,
            _callerContext.Role);

        var auditEntry = AuditEntry.Create(
            _callerContext.UserId,
            "authorization.refused",
            nameof(AdministratorOnlyRequirement),
            _callerContext.UserId.Value.ToString(),
            _clock);

        // No later use-case save exists to piggyback on: RequireAdministratorFilter returns
        // Results.Forbid() the moment AuthorizeAsync fails, and no use case (which would otherwise
        // call SaveChangesAsync) ever runs for a refused request. RecordAndSaveAsync (unlike
        // RecordAsync, used by other use cases) stages AND saves in one call for exactly this
        // reason. Any exception here — including from the save itself — is left to propagate: per
        // this handler's own "crash loud, don't guess" philosophy (see the ICallerContext remarks
        // above), a refusal whose audit trail failed to persist must not silently return 403 as if
        // everything worked; letting it propagate turns it into a fail-closed 500 via
        // ProblemDetailsHandler instead.
        await _auditWriter.RecordAndSaveAsync(auditEntry, CancellationToken.None);
    }
}
