using AwesomeAssertions;
using Microsoft.Extensions.Diagnostics.HealthChecks;
using Identity.Api.HealthChecks;
using Xunit;

namespace Identity.UnitTests.Observability;

/// <summary>
/// FR-008's third health state ("not-yet-ready") lives entirely in <see cref="StartupHealthCheck"/>
/// plus <see cref="StartupState"/>: given the flag is false, the check must report
/// <see cref="HealthStatus.Unhealthy"/> with a description that distinguishes "still starting"
/// from a genuine dependency failure; once the flag flips true, it must report
/// <see cref="HealthStatus.Healthy"/>. This is a pure unit test of that logic — see
/// <c>tests/Identity.IntegrationTests/Observability/HealthCheckTests.cs</c>'s remarks for why the
/// equivalent "hit /health/ready while startup is still running" scenario is not exercised
/// end-to-end in this codebase's test harness.
/// </summary>
public sealed class StartupHealthCheckTests
{
    [Fact]
    public async Task CheckHealthAsync_GivenStartupStateNotReady_ReportsUnhealthyWithStartupDescription()
    {
        var startupState = new StartupState();
        var check = new StartupHealthCheck(startupState);

        var result = await check.CheckHealthAsync(
            new HealthCheckContext(), TestContext.Current.CancellationToken);

        result.Status.Should().Be(HealthStatus.Unhealthy);
        result.Description.Should().Be("Startup not yet complete");
    }

    [Fact]
    public async Task CheckHealthAsync_GivenStartupStateReady_ReportsHealthy()
    {
        var startupState = new StartupState();
        startupState.MarkReady();
        var check = new StartupHealthCheck(startupState);

        var result = await check.CheckHealthAsync(
            new HealthCheckContext(), TestContext.Current.CancellationToken);

        result.Status.Should().Be(HealthStatus.Healthy);
    }

    [Fact]
    public async Task CheckHealthAsync_GivenStartupStateDraining_ReportsUnhealthyWithShuttingDownDescription()
    {
        var startupState = new StartupState();
        startupState.MarkReady();
        startupState.MarkStopping();
        var check = new StartupHealthCheck(startupState);

        var result = await check.CheckHealthAsync(
            new HealthCheckContext(), TestContext.Current.CancellationToken);

        result.Status.Should().Be(HealthStatus.Unhealthy);
        result.Description.Should().Be("Shutting down");
    }

    [Fact]
    public async Task CheckHealthAsync_GivenTerminationBeforeReadiness_ReportsDrainingNotReady()
    {
        // Edge case 3: a termination signal arriving before startup finished. The container
        // must exit cleanly having never advertised readiness.
        var startupState = new StartupState();
        startupState.MarkStopping();
        var check = new StartupHealthCheck(startupState);

        var result = await check.CheckHealthAsync(
            new HealthCheckContext(), TestContext.Current.CancellationToken);

        result.Status.Should().Be(HealthStatus.Unhealthy);
        result.Description.Should().Be("Shutting down");
    }

    [Fact]
    public void MarkReady_AfterMarkStopping_DoesNotResurrectReadiness()
    {
        // data-model.md §1's one real hazard: Program.cs calls MarkReady() unconditionally
        // after startup work, and a SIGTERM during startup makes MarkStopping() and a
        // late-arriving MarkReady() race. Draining must win regardless of ordering.
        var startupState = new StartupState();

        startupState.MarkStopping();
        startupState.MarkReady();

        startupState.IsDraining.Should().BeTrue();
        startupState.IsReady.Should().BeFalse();
    }
}
