using AwesomeAssertions;
using Microsoft.AspNetCore.Authorization;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Logging.Abstractions;
using Tenancy.Api.Authorization;
using Tenancy.Application.Abstractions;
using Tenancy.Domain.Abstractions;
using Xunit;

namespace Tenancy.UnitTests.Authorization;

/// <summary>
/// Unit tests for <see cref="AdministratorOnlyAuthorizationHandler"/> (T085), using ASP.NET
/// Core's own test-friendly <see cref="AuthorizationHandlerContext"/> construction directly — no
/// full HTTP pipeline needed — with a hand-rolled fake <see cref="ITenantContext"/> following
/// <c>RemoveMemberTests</c>' (T076) established convention.
/// </summary>
public class AdministratorOnlyAuthorizationHandlerTests
{
    private static readonly TenantId TestTenantId = new(Guid.CreateVersion7());

    private sealed class FakeTenantContext : ITenantContext
    {
        public TenantId TenantId => TestTenantId;

        public Role Role { get; init; }
    }

    /// <summary>
    /// Fake standing in for "the tenant context was never resolved" — mirrors
    /// <c>HttpContextTenantContext</c>'s documented contract (see <see cref="ITenantContext"/>'s
    /// remarks) that both properties must throw, never return a default value, if accessed
    /// before <c>TenantContextResolutionMiddleware</c> (T035) has populated them.
    /// </summary>
    private sealed class UnresolvedTenantContext : ITenantContext
    {
        public TenantId TenantId => throw new InvalidOperationException("Tenant context has not been resolved.");

        public Role Role => throw new InvalidOperationException("Tenant context has not been resolved.");
    }

    /// <summary>
    /// Minimal capturing fake for <see cref="ILogger{TCategoryName}"/> — following this test
    /// file's own established pattern of hand-rolled fakes over a mocking library — used to prove
    /// the FR-025 authorization-refusal log call actually fires with templated arguments, not
    /// string interpolation.
    /// </summary>
    private sealed class CapturingLogger : ILogger<AdministratorOnlyAuthorizationHandler>
    {
        public List<string> Messages { get; } = [];

        public IDisposable? BeginScope<TState>(TState state) where TState : notnull => null;

        public bool IsEnabled(LogLevel logLevel) => true;

        public void Log<TState>(
            LogLevel logLevel,
            EventId eventId,
            TState state,
            Exception? exception,
            Func<TState, Exception?, string> formatter)
        {
            Messages.Add(formatter(state, exception));
        }
    }

    private static async Task<AuthorizationHandlerContext> EvaluateAsync(
        ITenantContext tenantContext,
        ILogger<AdministratorOnlyAuthorizationHandler>? logger = null)
    {
        var handler = new AdministratorOnlyAuthorizationHandler(
            tenantContext,
            logger ?? NullLogger<AdministratorOnlyAuthorizationHandler>.Instance);
        var requirement = new AdministratorOnlyRequirement();
        var context = new AuthorizationHandlerContext(
            [requirement],
            new System.Security.Claims.ClaimsPrincipal(),
            resource: null);

        await handler.HandleAsync(context);
        return context;
    }

    [Fact]
    public async Task HandleRequirementAsync_AdministratorRole_Succeeds()
    {
        var context = await EvaluateAsync(new FakeTenantContext { Role = Role.Administrator });

        context.HasSucceeded.Should().BeTrue();
    }

    [Theory]
    [InlineData(Role.Member)]
    [InlineData(Role.Reader)]
    public async Task HandleRequirementAsync_NonAdministratorRole_Fails(Role role)
    {
        var context = await EvaluateAsync(new FakeTenantContext { Role = role });

        context.HasSucceeded.Should().BeFalse();
    }

    /// <summary>
    /// FR-025 gap closure: a role-based refusal must produce a structured log entry — tenant id,
    /// required role, and actual role — via a templated <c>LogWarning</c> call, not string
    /// interpolation. Mirrors <c>TenantContextResolutionMiddleware</c>'s (T059) established
    /// logging convention for the earlier "not a member at all" refusal path.
    /// </summary>
    [Fact]
    public async Task HandleRequirementAsync_NonAdministratorRole_LogsAuthorizationRefusal()
    {
        var logger = new CapturingLogger();

        var context = await EvaluateAsync(new FakeTenantContext { Role = Role.Member }, logger);

        context.HasSucceeded.Should().BeFalse();
        logger.Messages.Should().ContainSingle(
            message => message.Contains("Authorization refused", StringComparison.Ordinal)
                && message.Contains(TestTenantId.Value.ToString(), StringComparison.OrdinalIgnoreCase)
                && message.Contains(nameof(Role.Administrator), StringComparison.Ordinal)
                && message.Contains(nameof(Role.Member), StringComparison.Ordinal));
    }

    /// <summary>
    /// Guards against a regression where the success path starts logging too — an authorization
    /// grant is not a refusal, and FR-025's refusal-logging requirement should not fire here.
    /// </summary>
    [Fact]
    public async Task HandleRequirementAsync_AdministratorRole_DoesNotLogRefusal()
    {
        var logger = new CapturingLogger();

        await EvaluateAsync(new FakeTenantContext { Role = Role.Administrator }, logger);

        logger.Messages.Should().BeEmpty();
    }

    [Fact]
    public async Task HandleRequirementAsync_UnresolvedTenantContext_PropagatesException()
    {
        // Documents T085's deliberate design decision: this handler does not guard against an
        // unresolved ITenantContext. ASP.NET Core's own pipeline ordering does not guarantee
        // TenantContextResolutionMiddleware (an IEndpointFilter, running as part of endpoint
        // invocation) has already run by the time a policy using this handler is evaluated by
        // AuthorizationMiddleware (registered earlier, via UseAuthorization()). Letting the
        // exception propagate here turns a broken precondition into a fail-closed 500 (via
        // ProblemDetailsHandler, T083) rather than silently succeeding or failing open.
        var act = () => EvaluateAsync(new UnresolvedTenantContext());

        await act.Should().ThrowAsync<InvalidOperationException>();
    }
}
