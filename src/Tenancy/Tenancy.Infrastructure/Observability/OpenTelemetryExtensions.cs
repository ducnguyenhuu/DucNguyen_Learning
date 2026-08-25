using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using OpenTelemetry.Logs;
using OpenTelemetry.Metrics;
using OpenTelemetry.Resources;
using OpenTelemetry.Trace;

namespace Tenancy.Infrastructure.Observability;

/// <summary>
/// Registers the OpenTelemetry tracing, metrics, and logging providers for the
/// Tenancy service, exporting all signals via OTLP.
/// </summary>
public static class OpenTelemetryExtensions
{
    private const string ServiceName = "Tenancy";

    public static IServiceCollection AddTenancyObservability(
        this IServiceCollection services,
        IConfiguration configuration)
    {
        services.AddOpenTelemetry()
            .ConfigureResource(resource => resource.AddService(ServiceName))
            .WithTracing(tracing => tracing
                // Tail-based sampling (FR-007) is decided by the Collector's
                // tail_sampling processor, which needs every span for a trace
                // to evaluate the error/success outcome after the fact. The
                // app itself must therefore never drop spans: explicitly use
                // AlwaysOnSampler rather than relying on the SDK's default
                // (which is also AlwaysOn, but implicit) so this invariant is
                // visible and can't regress silently.
                .SetSampler(new AlwaysOnSampler())
                .AddAspNetCoreInstrumentation()
                .AddSqlClientInstrumentation()
                .AddOtlpExporter())
            .WithMetrics(metrics => metrics.AddOtlpExporter())
            .WithLogging(logging => { }, options => options.AddOtlpExporter());

        return services;
    }
}
