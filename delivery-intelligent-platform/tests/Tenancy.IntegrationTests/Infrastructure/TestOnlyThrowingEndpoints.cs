using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Routing;
using Tenancy.Domain.Abstractions;

namespace Tenancy.IntegrationTests.Infrastructure;

/// <summary>
/// Registers two test-only routes that deliberately throw an unhandled
/// <see cref="DomainException"/>/<see cref="ConflictException"/>, for the sole purpose of proving
/// what the production global exception handler (<c>ProblemDetailsHandler</c>) actually does with
/// those exception types.
/// </summary>
/// <remarks>
/// Every real production endpoint (<c>TenantEndpoints</c>, <c>InvitationEndpoints</c>,
/// <c>MemberEndpoints</c>) already catches <see cref="DomainException"/>/<see cref="ConflictException"/>
/// locally and translates it to a specific status code before it can ever reach the global
/// handler — so there is no existing real route whose unhandled-exception path can be used to
/// exercise the handler's own <see cref="DomainException"/>/<see cref="ConflictException"/>
/// mapping end-to-end. These routes exist only in the test host (wired via
/// <see cref="ApiFactory"/>'s <c>IStartupFilter</c> registration below, never referenced from
/// <c>Tenancy.Api</c>'s own <c>Program.cs</c>) so that an integration test can still make a real
/// HTTP call that reaches the same middleware pipeline, including the real
/// <c>UseExceptionHandler()</c> registration, and observe the real response.
/// </remarks>
public static class TestOnlyThrowingEndpoints
{
    public const string DomainExceptionPath = "/test-only/throws-domain-exception";

    public const string ConflictExceptionPath = "/test-only/throws-conflict-exception";

    public static void Map(IEndpointRouteBuilder endpoints)
    {
        endpoints.MapGet(DomainExceptionPath, () =>
        {
            throw new DomainException("Deliberate, test-only unhandled DomainException.");
        });

        endpoints.MapGet(ConflictExceptionPath, () =>
        {
            throw new ConflictException("Deliberate, test-only unhandled ConflictException.");
        });
    }
}

/// <summary>
/// Appends <see cref="TestOnlyThrowingEndpoints"/>'s routes to the test host's endpoint route
/// table, after the rest of the pipeline (built by <c>Tenancy.Api</c>'s own <c>Program.cs</c>) has
/// configured routing — so these test-only routes still flow through the same
/// <c>UseExceptionHandler()</c> middleware every real route does.
/// </summary>
public sealed class TestOnlyThrowingEndpointsStartupFilter : IStartupFilter
{
    public Action<IApplicationBuilder> Configure(Action<IApplicationBuilder> next)
    {
        return app =>
        {
            next(app);

            app.UseEndpoints(endpoints => TestOnlyThrowingEndpoints.Map(endpoints));
        };
    }
}
