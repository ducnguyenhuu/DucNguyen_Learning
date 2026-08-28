using Microsoft.Extensions.Diagnostics.HealthChecks;

namespace Tenancy.Api.HealthChecks;

/// <summary>
/// FR-008's third health state: "not-yet-ready" (startup/initialization incomplete), distinct
/// from both healthy and unhealthy-dependency. Reports <see cref="HealthStatus.Unhealthy"/> with
/// a description that a human (reading <c>/health/ready</c>'s body, not an automated router —
/// see <c>contracts/health-endpoints.md</c>) can distinguish from a genuine dependency failure,
/// until <see cref="StartupState.IsReady"/> flips true; <see cref="HealthStatus.Healthy"/>
/// afterward.
/// </summary>
public sealed class StartupHealthCheck : IHealthCheck
{
    private readonly StartupState _startupState;

    public StartupHealthCheck(StartupState startupState)
    {
        _startupState = startupState;
    }

    public Task<HealthCheckResult> CheckHealthAsync(
        HealthCheckContext context,
        CancellationToken cancellationToken = default)
    {
        var result = _startupState.IsReady
            ? HealthCheckResult.Healthy()
            : HealthCheckResult.Unhealthy("Startup not yet complete");

        return Task.FromResult(result);
    }
}
