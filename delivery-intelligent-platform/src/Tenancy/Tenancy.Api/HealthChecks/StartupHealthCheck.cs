using Microsoft.Extensions.Diagnostics.HealthChecks;

namespace Tenancy.Api.HealthChecks;

/// <summary>
/// Reports <see cref="StartupState"/>'s three phases on <c>/health/ready</c> with wording a
/// human reading the response body (not an automated router — see
/// <c>contracts/health-endpoints.md</c>) can tell apart: not-yet-started, ready, and
/// draining. <see cref="HealthStatus"/> has only three values and none of them means
/// "shutting down", so draining is reported as <see cref="HealthStatus.Unhealthy"/> with
/// distinct wording from the startup-incomplete case — both leave the container correctly
/// refusing new traffic, but only one of them is a normal, expected shutdown.
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
        var result = _startupState switch
        {
            { IsDraining: true } => HealthCheckResult.Unhealthy("Shutting down"),
            { IsReady: true } => HealthCheckResult.Healthy(),
            _ => HealthCheckResult.Unhealthy("Startup not yet complete"),
        };

        return Task.FromResult(result);
    }
}
