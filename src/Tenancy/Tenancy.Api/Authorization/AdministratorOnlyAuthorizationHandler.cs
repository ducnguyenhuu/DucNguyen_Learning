using Microsoft.AspNetCore.Authorization;
using Microsoft.Extensions.Logging;
using Tenancy.Application.Abstractions;
using Tenancy.Domain.Abstractions;

namespace Tenancy.Api.Authorization;

/// <summary>
/// Evaluates <see cref="AdministratorOnlyRequirement"/> against <see cref="ITenantContext.Role"/>
/// — the role resolved from the caller's real, active <c>Membership</c> row in the candidate
/// tenant (see <c>TenantContextResolutionMiddleware</c>, T035) — never against any claim on
/// <c>HttpContext.User</c>. Reading a token claim here would defeat ADR-017 step 5's whole point:
/// a claim is the caller's own assertion, whereas the resolved membership is the source of truth
/// this handler must check instead.
/// </summary>
/// <remarks>
/// <para>
/// <b>Ordering / fail-closed behavior:</b> <see cref="ITenantContext"/> throws
/// <see cref="InvalidOperationException"/> if read before it has been resolved for the current
/// request (see <c>HttpContextTenantContext</c>). This handler makes <b>no attempt</b> to catch
/// that and does <b>not</b> guard against it — it lets the exception propagate.
/// </para>
/// <para>
/// This is a deliberate choice, not an oversight: ASP.NET Core's own pipeline ordering does
/// <b>not</b> guarantee tenant context resolution has already happened by the time a policy using
/// this handler is evaluated. <c>TenantContextResolutionMiddleware</c> is an
/// <see cref="Microsoft.AspNetCore.Http.IEndpointFilter"/> (T035's own reasoning explains why:
/// it needs the matched route value, which only exists after routing), and endpoint filters run
/// as part of endpoint invocation — <i>after</i> <c>UseAuthorization()</c>'s middleware has
/// already run. So a policy applied the conventional way (e.g. via an
/// <c>[Authorize(Policy = "TenantAdministrator")]</c> route metadata attribute, evaluated by
/// <c>AuthorizationMiddleware</c>) would run <b>before</b> this filter ever populates
/// <see cref="ITenantContext"/>, and this handler would always observe it unresolved.
/// </para>
/// <para>
/// Given that, whichever endpoint (T088) applies this policy is responsible for ensuring it is
/// evaluated only after tenant context resolution — e.g. by invoking
/// <c>IAuthorizationService.AuthorizeAsync</c> explicitly from within an endpoint filter chained
/// after <c>TenantContextResolutionMiddleware</c>, rather than relying on the
/// <c>[Authorize]</c>-attribute/middleware path. This task does not decide that wiring (T088's
/// job); it only decides what happens here, in the handler, if that responsibility is ever
/// dropped: letting <see cref="ITenantContext"/>'s exception propagate turns an unresolved
/// tenant context into an unhandled exception, which <c>ProblemDetailsHandler</c> (T083) turns
/// into a fail-closed 500 — never into a silent "succeeds" or "fails open" default. That is the
/// only acceptable behavior for a security check with a broken precondition: crash loud, don't
/// guess.
/// </para>
/// </remarks>
public sealed class AdministratorOnlyAuthorizationHandler
    : AuthorizationHandler<AdministratorOnlyRequirement>
{
    private readonly ITenantContext _tenantContext;
    private readonly ILogger<AdministratorOnlyAuthorizationHandler> _logger;

    public AdministratorOnlyAuthorizationHandler(
        ITenantContext tenantContext,
        ILogger<AdministratorOnlyAuthorizationHandler> logger)
    {
        _tenantContext = tenantContext;
        _logger = logger;
    }

    protected override Task HandleRequirementAsync(
        AuthorizationHandlerContext context,
        AdministratorOnlyRequirement requirement)
    {
        if (_tenantContext.Role == Role.Administrator)
        {
            context.Succeed(requirement);
        }
        else
        {
            // FR-025's "authorization refusal" category: this is the only place in the
            // request pipeline that knows both *why* the caller was refused (their actual,
            // membership-resolved role) and the tenant the refusal happened in — the calling
            // filter (RequireTenantAdministratorFilter) only ever sees a bare
            // AuthorizationResult.Succeeded == false, with no role detail to log. Logging here,
            // not there, keeps the log entry as close as possible to the actual decision.
            // ITenantContext exposes no UserId, so the caller's identity is read from the "oid"
            // claim already on this AuthorizationHandlerContext — the same claim
            // TenantContextResolutionMiddleware (T035/T059) uses to identify the caller, never an
            // email or token. Only ids/role are logged — matching the same "no unnecessary
            // personal data" discipline already established there and by CreateTenant/RemoveMember
            // (T089).
            var callerObjectId = context.User.FindFirst("oid")?.Value;
            _logger.LogWarning(
                "Authorization refused: tenant {TenantId}, user {UserId}, required role {RequiredRole}, actual role {ActualRole}",
                _tenantContext.TenantId,
                callerObjectId,
                Role.Administrator,
                _tenantContext.Role);
        }

        return Task.CompletedTask;
    }
}
