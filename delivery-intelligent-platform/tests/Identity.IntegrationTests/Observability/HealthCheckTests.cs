using System.Net;
using AwesomeAssertions;
using Microsoft.Extensions.DependencyInjection;
using Identity.Api.HealthChecks;
using Identity.IntegrationTests.Infrastructure;
using Xunit;

namespace Identity.IntegrationTests.Observability;

/// <summary>
/// FR-008: liveness and readiness endpoints for infrastructure probes, per
/// <c>specs/003-observability/contracts/health-endpoints.md</c>.
/// </summary>
/// <remarks>
/// <para>
/// <b>Coverage of FR-008's three states.</b> This class exercises "healthy"
/// (<see cref="GetHealthLive_ReturnsHealthy"/>, and the first half of
/// <see cref="GetHealthReady_ReflectsSqlServerReachability"/>) and "unhealthy, dependency named"
/// (the second half of the same test, via the SQL Server container stop/restart below). The
/// third state — "not-yet-ready" (startup/initialization incomplete) — is deliberately not
/// exercised end-to-end here: <c>Program.cs</c> marks <c>StartupState</c> ready before
/// <c>app.Run()</c> starts listening, so there is no window in which an HTTP client (including
/// <c>ApiFactory</c>'s in-memory <c>TestServer</c>) can observe the process while that flag is
/// still false — the race this state exists to cover is over before the server accepts its first
/// request. That state's logic (does the health check report the right status/description given
/// the flag's value) is instead covered by a focused unit test:
/// <c>tests/Identity.UnitTests/Observability/StartupHealthCheckTests.cs</c>. See
/// <c>specs/003-observability/quickstart.md</c>'s requirement-coverage table for FR-008, which
/// cites both.
/// </para>
/// <para>
/// <b>Why the SQL Server container is stopped and restarted inside a single test.</b> The
/// contract requires <c>/health/ready</c> to report 503 Unhealthy, naming <c>"sqlserver"</c>, when
/// SQL Server is unreachable. The only way to exercise that against a real dependency check (as
/// opposed to a fake/mocked one) is to make the real SQL Server actually unreachable — so this
/// test stops the shared <see cref="SqlServerFixture"/> container for the span of one assertion.
/// That container is shared (one per assembly, not per test class — see
/// <see cref="SqlServerFixture"/>'s remarks) by every other test class in this assembly, so
/// leaving it stopped would cascade-fail unrelated tests. The stop/assert/restart sequence is
/// wrapped in a <c>try/finally</c> so the container is guaranteed to be running again before this
/// test returns, regardless of whether the assertion passes or throws.
/// </para>
/// </remarks>
public sealed class HealthCheckTests : IdentityIntegrationTestBase
{
    private readonly SqlServerFixture _sqlServerFixture;

    public HealthCheckTests(SqlServerFixture sqlServerFixture, ApiFactory factory)
        : base(sqlServerFixture, factory)
    {
        _sqlServerFixture = sqlServerFixture;
    }

    /// <summary>
    /// <c>/health/live</c> reports the process is up, unconditionally — it is not supposed to
    /// depend on SQL Server (or anything else, including the "startup" check) being reachable
    /// or complete.
    /// </summary>
    [Fact]
    public async Task GetHealthLive_ReturnsHealthy()
    {
        using var client = Factory.CreateClient();

        using var response = await client.GetAsync(
            "/health/live",
            TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(
            HttpStatusCode.OK,
            "liveness must report 200 whenever the process itself can respond at all, " +
            "independent of any dependency's health");

        var body = await response.Content.ReadAsStringAsync(TestContext.Current.CancellationToken);
        body.Should().Contain("Healthy");
    }

    /// <summary>
    /// <c>/health/ready</c> reports 200 Healthy (naming <c>"sqlserver"</c>) while SQL Server is
    /// reachable, then 503 Unhealthy (still naming <c>"sqlserver"</c>) once the shared container
    /// is stopped — and restores the container before returning, via <c>try/finally</c>, so no
    /// other test in the assembly is affected.
    /// </summary>
    [Fact]
    public async Task GetHealthReady_ReflectsSqlServerReachability()
    {
        using var client = Factory.CreateClient();

        using var healthyResponse = await client.GetAsync(
            "/health/ready",
            TestContext.Current.CancellationToken);

        healthyResponse.StatusCode.Should().Be(
            HttpStatusCode.OK,
            "readiness must report 200 Healthy while SQL Server is reachable");
        var healthyBody = await healthyResponse.Content.ReadAsStringAsync(
            TestContext.Current.CancellationToken);
        healthyBody.Should().Contain("sqlserver");
        healthyBody.Should().Contain("startup");
        healthyBody.Should().Contain("Healthy");

        try
        {
            await _sqlServerFixture.StopAsync();

            using var unhealthyResponse = await client.GetAsync(
                "/health/ready",
                TestContext.Current.CancellationToken);

            unhealthyResponse.StatusCode.Should().Be(
                HttpStatusCode.ServiceUnavailable,
                "readiness must report 503 Unhealthy once SQL Server is unreachable");
            var unhealthyBody = await unhealthyResponse.Content.ReadAsStringAsync(
                TestContext.Current.CancellationToken);
            unhealthyBody.Should().Contain("sqlserver");
            unhealthyBody.Should().Contain("Unhealthy");
        }
        finally
        {
            // Guaranteed restart: every other test class in this assembly shares this same
            // container instance (see SqlServerFixture's remarks), so leaving it stopped here
            // would cascade-fail every other integration test in the assembly.
            await _sqlServerFixture.StartAsync();
        }
    }

    /// <summary>
    /// The draining state (data-model.md §1): once <see cref="StartupState.MarkStopping"/> has
    /// run, <c>/health/ready</c> must report 503 with wording distinct from both "healthy" and
    /// "startup not yet complete", while <c>/health/live</c> stays 200 — a draining container
    /// must not look dead, or an orchestrator restarts it mid-drain.
    /// </summary>
    /// <remarks>
    /// <see cref="StartupState"/>'s transition to draining is one-way and terminal by design
    /// (see its remarks), so this test builds its own throwaway <see cref="ApiFactory"/> rather
    /// than mutating <see cref="IdentityIntegrationTestBase.Factory"/> — that instance is shared
    /// across every <c>[Fact]</c> in this class via <c>IClassFixture&lt;ApiFactory&gt;</c>, and
    /// xUnit v3 does not guarantee method execution order (see
    /// <see cref="IdentityIntegrationTestBase"/>'s remarks), so permanently draining the shared
    /// instance would make <see cref="GetHealthReady_ReflectsSqlServerReachability"/> fail
    /// whenever it happens to run afterward. This also means a real SIGTERM/
    /// <c>ApplicationStopping</c> sequence is not exercised here, for the same reason the
    /// "not-yet-ready" state above is unit-tested rather than driven end-to-end — see
    /// <c>tests/Identity.UnitTests/Observability/StartupHealthCheckTests.cs</c>, which covers
    /// that <c>Program.cs</c> wires <c>MarkStopping()</c> to the real
    /// <c>ApplicationStopping</c> callback is a one-line fact, not logic this test needs to
    /// re-prove; what this integration test adds is that the HTTP pipeline actually surfaces
    /// draining with the right status code and body.
    /// </remarks>
    [Fact]
    public async Task GetHealthReady_WhileDraining_ReportsUnhealthyShuttingDown_WhileLiveStaysHealthy()
    {
        using var drainingFactory = new ApiFactory();
        drainingFactory.UseConnectionString(_sqlServerFixture.ConnectionString);
        using var client = drainingFactory.CreateClient();

        drainingFactory.Services.GetRequiredService<StartupState>().MarkStopping();

        using var readyResponse = await client.GetAsync(
            "/health/ready",
            TestContext.Current.CancellationToken);

        readyResponse.StatusCode.Should().Be(HttpStatusCode.ServiceUnavailable);
        var readyBody = await readyResponse.Content.ReadAsStringAsync(
            TestContext.Current.CancellationToken);
        readyBody.Should().Contain("Shutting down");

        using var liveResponse = await client.GetAsync(
            "/health/live",
            TestContext.Current.CancellationToken);

        liveResponse.StatusCode.Should().Be(
            HttpStatusCode.OK,
            "a draining container is not dead — liveness must stay healthy so an " +
            "orchestrator does not restart it mid-drain");
    }
}
