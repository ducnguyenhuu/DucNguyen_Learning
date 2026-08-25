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
            .WithTracing(tracing => tracing.AddOtlpExporter())
            .WithMetrics(metrics => metrics.AddOtlpExporter())
            .WithLogging(logging => { }, options => options.AddOtlpExporter());

        return services;
    }
}
