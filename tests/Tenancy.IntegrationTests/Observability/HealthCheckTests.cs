using System.Net;
using AwesomeAssertions;
using Tenancy.IntegrationTests.Infrastructure;
using Xunit;

namespace Tenancy.IntegrationTests.Observability;

/// <summary>
/// T026 + T027 (Phase 4, User Story 2), FR-008: liveness and readiness endpoints for
/// infrastructure probes, per <c>specs/003-observability/contracts/health-endpoints.md</c>.
/// </summary>
/// <remarks>
/// <para>
/// <b>Written before the routes exist.</b> No health-check middleware/endpoints are registered
/// yet — that is T028/T030 (separate, later tasks). Both tests here are expected to fail against
/// the current codebase (404 Not Found, since neither route exists), and will start passing once
/// T028/T030 land.
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
public sealed class HealthCheckTests : TenancyIntegrationTestBase
{
    private readonly SqlServerFixture _sqlServerFixture;

    public HealthCheckTests(SqlServerFixture sqlServerFixture, ApiFactory factory)
        : base(sqlServerFixture, factory)
    {
        _sqlServerFixture = sqlServerFixture;
    }

    /// <summary>
    /// T026: <c>/health/live</c> reports the process is up, unconditionally — it is not supposed
    /// to depend on SQL Server (or anything else) being reachable.
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
    /// T027: <c>/health/ready</c> reports 200 Healthy (naming <c>"sqlserver"</c>) while SQL
    /// Server is reachable, then 503 Unhealthy (still naming <c>"sqlserver"</c>) once the shared
    /// container is stopped — and restores the container before returning, via
    /// <c>try/finally</c>, so no other test in the assembly is affected.
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
}
