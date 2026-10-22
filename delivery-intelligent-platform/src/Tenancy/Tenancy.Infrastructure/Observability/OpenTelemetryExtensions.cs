using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using OpenTelemetry;
using OpenTelemetry.Exporter;
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

    /// <summary>
    /// Configuration key that points the OTLP exporter at a specific endpoint, overriding the
    /// OpenTelemetry .NET SDK's own default/env-var resolution (which otherwise defaults to
    /// <c>http://localhost:4317</c> or honors <c>OTEL_EXPORTER_OTLP_ENDPOINT</c>). A test host
    /// sets this via an in-memory <see cref="IConfiguration"/> source added before the host is
    /// built; it is equally the mechanism for switching between the local Collector
    /// (`deploy/otel-collector/`) and New Relic's OTLP endpoint in any environment — always a
    /// configuration change, never a code branch. Left unset, the SDK's own default applies
    /// (the local Collector for local dev).
    /// </summary>
    public const string OtlpEndpointConfigurationKey = "Observability:OtlpEndpoint";

    /// <summary>
    /// Configuration key for the New Relic OTLP ingest API key (New Relic's documented
    /// "Ingest - License Key" type). Read via <see cref="IConfiguration"/> only — never
    /// hardcoded and never present in <c>appsettings.json</c>/<c>appsettings.Development.json</c>
    /// (Constitution Principle V). Locally this is set via .NET User Secrets for the
    /// <c>Tenancy.Api</c> project, matching the existing convention for the SQL Server
    /// connection string (see quickstart.md §6). Once this service is deployed to AKS, the
    /// same key is resolved from Azure Key Vault via workload identity instead — the
    /// <see cref="IConfiguration"/> read here does not change, only where the value comes
    /// from (infrastructure/deployment concern, not application code).
    /// When unset (the local-dev default), no header is added and the exporter talks to the
    /// local Collector exactly as before — switching backends is a configuration change only,
    /// never a code branch.
    /// </summary>
    public const string NewRelicApiKeyConfigurationKey = "Observability:NewRelicApiKey";

    public static IServiceCollection AddTenancyObservability(
        this IServiceCollection services,
        IConfiguration configuration)
    {
        // FR-006: a telemetry export failure or backend unavailability must never fail, block,
        // or measurably slow a request. This is applied to every OTLP exporter registration
        // below rather than left implicit:
        //   - ExportProcessorType.Batch (traces/logs): exports happen on a background thread in
        //     batches, never synchronously on the thread handling the request. This is already
        //     the OpenTelemetry .NET SDK's own default for AddOtlpExporter() — confirmed against
        //     the installed OpenTelemetry.Exporter.OpenTelemetryProtocol 1.16.0 package
        //     (OtlpExporterOptions.ExportProcessorType defaults to ExportProcessorType.Batch) —
        //     but set explicitly here so the invariant is visible in this codebase rather than
        //     resting on an SDK default that could silently change.
        //   - TimeoutMilliseconds: the per-export-attempt timeout passed to the OTLP client.
        //     10 seconds is also the SDK's own default (confirmed the same way), which is
        //     reasonable for a background batch export and never blocks a request thread; set
        //     explicitly for the same visibility reason.
        // Metrics use a PeriodicExportingMetricReader by default when registered via
        // .WithMetrics(...).AddOtlpExporter() (there is no synchronous "export on read" reader
        // wired up here), which is likewise inherently off the request path and needs no
        // processor-type override.
        void ConfigureOtlpExporter(OtlpExporterOptions options)
        {
            options.ExportProcessorType = ExportProcessorType.Batch;
            options.TimeoutMilliseconds = 10_000;

            // Endpoint override hook (see OtlpEndpointConfigurationKey). A test host sets this
            // via an in-memory configuration source; local dev leaves it unset, so the SDK's
            // normal endpoint resolution (OTEL_EXPORTER_OTLP_ENDPOINT env var, else
            // http://localhost:4317) applies unchanged and points at the local Collector.
            var endpointOverride = configuration[OtlpEndpointConfigurationKey];
            if (!string.IsNullOrWhiteSpace(endpointOverride))
            {
                options.Endpoint = new Uri(endpointOverride);
            }

            // New Relic's OTLP ingest requires the license key sent as an "api-key" header
            // (New Relic's documented OTLP setup, not a code branch — see
            // NewRelicApiKeyConfigurationKey). Absent locally, so this is a no-op and the
            // exporter talks to the local Collector without any header, as before.
            var newRelicApiKey = configuration[NewRelicApiKeyConfigurationKey];
            if (!string.IsNullOrWhiteSpace(newRelicApiKey))
            {
                options.Headers = $"api-key={newRelicApiKey}";
            }
        }

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
                .AddOtlpExporter(ConfigureOtlpExporter))
            .WithMetrics(metrics => metrics.AddOtlpExporter(ConfigureOtlpExporter))
            .WithLogging(logging => { }, options => options.AddOtlpExporter(ConfigureOtlpExporter));

        return services;
    }
}
