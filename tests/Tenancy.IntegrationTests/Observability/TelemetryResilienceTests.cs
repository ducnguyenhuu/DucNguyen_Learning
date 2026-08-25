using System.Diagnostics;
using System.Net;
using System.Net.Http.Headers;
using System.Net.Sockets;
using AwesomeAssertions;
using Tenancy.IntegrationTests.Infrastructure;
using Xunit;

namespace Tenancy.IntegrationTests.Observability;

/// <summary>
/// T024 (Phase 3, User Story 1), FR-006: "A telemetry export failure or backend unavailability
/// MUST NOT cause a request to fail, block, or slow down beyond a bounded, small overhead —
/// telemetry emission is fire-and-forget from the request's perspective."
/// </summary>
/// <remarks>
/// <para>
/// <b>Why this is expected to already pass.</b> <c>OpenTelemetryExtensions</c>
/// (<c>AddTenancyObservability</c>) explicitly sets <c>ExportProcessorType.Batch</c> and a
/// bounded 10-second <c>TimeoutMilliseconds</c> on every OTLP exporter registration (traces,
/// logs, metrics) — confirmed against the installed OpenTelemetry SDK 1.16.0 packages to already
/// be the SDK's own default, and made explicit here rather than left implicit. A batch processor
/// hands completed spans/log records to a background thread and returns immediately; the
/// exporter's own connection attempt/timeout to an unreachable OTLP endpoint happens entirely on
/// that background thread, never on the thread handling this test's HTTP request. This test is
/// the proof, not the fix.
/// </para>
/// <para>
/// <b>Why an unused local TCP port, not a firewalled/black-holed address.</b> A port nothing is
/// listening on causes the OTLP gRPC client's connection attempt to fail fast (connection
/// refused) rather than hang until a network-level timeout — which is actually the harder case
/// for this test to get wrong: even an immediate, repeated connection-refused failure on every
/// batch flush must not leak onto the request path or measurably slow it down.
/// </para>
/// </remarks>
public sealed class TelemetryResilienceTests : TenancyIntegrationTestBase
{
    public TelemetryResilienceTests(SqlServerFixture sqlServerFixture, ApiFactory factory)
        : base(sqlServerFixture, factory)
    {
        // Must happen before the host is first built (before CreateClient()/Server is touched),
        // same constraint as ApiFactory.UseConnectionString — see that method's remarks.
        Factory.UseOtlpEndpoint($"http://127.0.0.1:{GetUnusedLocalPort()}");
    }

    /// <summary>
    /// Finds a TCP port on localhost nothing is currently listening on, by binding a listener to
    /// port 0 (OS-assigned free port) and immediately releasing it. There is an inherent, narrow
    /// race between releasing the port here and the OTLP exporter later attempting to connect to
    /// it — acceptable for this test, since the assertion under test (request latency/success)
    /// does not depend on the connection attempt failing for any particular reason, only on
    /// nothing genuinely useful being reachable there.
    /// </summary>
    private static int GetUnusedLocalPort()
    {
        using var listener = new TcpListener(IPAddress.Loopback, 0);
        listener.Start();
        var port = ((IPEndPoint)listener.LocalEndpoint).Port;
        listener.Stop();
        return port;
    }

    /// <summary>
    /// T024's acceptance test: a normal, existing request (<c>GET /tenants/{tenantId}</c>) must
    /// still succeed and complete promptly even though the OTLP exporter is configured to point
    /// at an address nothing is listening on. A generous upper bound (well under the exporter's
    /// own 10-second <c>TimeoutMilliseconds</c>) is used for the latency assertion — the point is
    /// not to pin down an exact number, but to catch the specific regression this task guards
    /// against: the request thread blocking on (or being slowed by) the unreachable exporter.
    /// </summary>
    [Fact]
    public async Task GetTenant_SucceedsPromptly_EvenWhenOtlpExporterEndpointIsUnreachable()
    {
        await Factory.InitializeDatabaseAsync();
        var seed = await Factory.SeedTwoTenantsAsync();

        using var client = Factory.CreateClient();
        using var request = new HttpRequestMessage(
            HttpMethod.Get,
            $"/tenants/{seed.TenantA.TenantId.Value}");
        request.Headers.Authorization = new AuthenticationHeaderValue("TestScheme", "test");
        request.Headers.Add("X-Test-Oid", seed.TenantA.EntraObjectId.ToString());
        request.Headers.Add("X-Test-Tid", seed.TenantA.EntraTenantId.ToString());

        var stopwatch = Stopwatch.StartNew();
        using var response = await client.SendAsync(request, TestContext.Current.CancellationToken);
        stopwatch.Stop();

        response.StatusCode.Should().Be(HttpStatusCode.OK);
        stopwatch.Elapsed.Should().BeLessThan(
            TimeSpan.FromSeconds(5),
            "an unreachable OTLP exporter endpoint must not block or measurably slow down the " +
            "request — telemetry export is fire-and-forget (FR-006)");
    }
}
