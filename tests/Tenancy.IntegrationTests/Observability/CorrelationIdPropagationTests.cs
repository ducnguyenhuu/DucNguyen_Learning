using System.Diagnostics;
using System.Net.Http.Headers;
using AwesomeAssertions;
using Tenancy.IntegrationTests.Infrastructure;
using Xunit;

namespace Tenancy.IntegrationTests.Observability;

/// <summary>
/// T015/T016 (Phase 3, User Story 1): tests written before the corresponding instrumentation
/// tasks (T019-T021) exist, per this codebase's TDD convention. They are expected to fail today
/// because no ASP.NET Core/SqlClient OpenTelemetry auto-instrumentation is wired into
/// <c>AddTenancyObservability</c> yet (see <c>OpenTelemetryExtensions</c>) — that wiring is
/// T019's job. Do not "fix" these tests by adding that instrumentation here.
/// </summary>
/// <remarks>
/// <para>
/// <b>How activities are captured without a real Collector.</b> An <see cref="ActivityListener"/>
/// is registered for the duration of each test and subscribes to every <see cref="ActivitySource"/>
/// (<c>ShouldListenTo = _ => true</c>), regardless of whether OpenTelemetry's SDK itself is
/// listening to that source. This observes <see cref="Activity"/> objects created by ASP.NET
/// Core's own built-in hosting diagnostics (which creates an <see cref="Activity"/> per request
/// unconditionally, independent of OpenTelemetry) and by <c>Microsoft.Data.SqlClient</c>'s own
/// diagnostics source (which only creates an <see cref="Activity"/> if something is listening to
/// it — an <see cref="ActivityListener"/> with <c>Sample</c> returning
/// <see cref="ActivitySamplingResult.AllDataAndRecorded"/> satisfies that "is anyone listening"
/// check, same as OpenTelemetry's own SDK would).
/// </para>
/// <para>
/// <b>What T015 actually needs from T019, and why it may or may not fail today.</b> The
/// correctness property under test is "the HTTP-server activity and the SQL-client activity for
/// one request share a single <c>TraceId</c>" — trace *connectivity*, not merely that either
/// activity individually exists. ASP.NET Core's hosting <see cref="Activity"/> establishes the
/// root of the trace for the request; whether SqlClient's own <see cref="Activity"/> is created
/// as a *child* of that same trace (sharing its <c>TraceId</c>) depends on
/// <see cref="Activity.Current"/> flowing correctly through the async call chain from the
/// controller/endpoint into the EF Core/SqlClient call — something the .NET runtime's ambient
/// <see cref="Activity.Current"/> propagation generally does on its own via
/// <see cref="System.Threading.ExecutionContext"/>, with no OpenTelemetry involvement at all. So
/// this test's TraceId-sharing assertion may already pass today purely from framework-level
/// ambient activity propagation, even before T019 wires OpenTelemetry's own
/// AddAspNetCoreInstrumentation/AddSqlClientInstrumentation packages — see this class's actual
/// test run output (reported alongside this file) for which outcome actually occurred, reported
/// honestly either way per this task's brief.
/// </para>
/// </remarks>
public sealed class CorrelationIdPropagationTests : TenancyIntegrationTestBase
{
    public CorrelationIdPropagationTests(SqlServerFixture sqlServerFixture, ApiFactory factory)
        : base(sqlServerFixture, factory)
    {
    }

    /// <summary>
    /// T015: a request that touches the database (<c>GET /tenants/{tenantId}</c>, an existing
    /// endpoint from spec 001/002) must produce one connected trace — at least one HTTP-server
    /// activity and at least one SQL-client activity, all sharing the same <c>TraceId</c>.
    /// </summary>
    [Fact]
    public async Task GetTenant_ProducesOneConnectedTrace_AcrossHttpAndSqlActivities()
    {
        await Factory.InitializeDatabaseAsync();
        var seed = await Factory.SeedTwoTenantsAsync();

        var capturedActivities = new System.Collections.Concurrent.ConcurrentQueue<Activity>();

        using var listener = new ActivityListener
        {
            ShouldListenTo = _ => true,
            Sample = (ref ActivityCreationOptions<ActivityContext> _) =>
                ActivitySamplingResult.AllDataAndRecorded,
            ActivityStopped = capturedActivities.Enqueue,
        };
        ActivitySource.AddActivityListener(listener);

        using var client = Factory.CreateClient();
        using var request = new HttpRequestMessage(
            HttpMethod.Get,
            $"/tenants/{seed.TenantA.TenantId.Value}");
        request.Headers.Authorization = new AuthenticationHeaderValue("TestScheme", "test");
        request.Headers.Add("X-Test-Oid", seed.TenantA.EntraObjectId.ToString());
        request.Headers.Add("X-Test-Tid", seed.TenantA.EntraTenantId.ToString());

        var response = await client.SendAsync(request, TestContext.Current.CancellationToken);
        response.EnsureSuccessStatusCode();

        var activities = capturedActivities.ToArray();

        var httpServerActivity = activities.FirstOrDefault(activity =>
            activity.Kind == ActivityKind.Server
            || activity.OperationName.Contains("Microsoft.AspNetCore", StringComparison.OrdinalIgnoreCase)
            || activity.DisplayName.Contains("HTTP GET", StringComparison.OrdinalIgnoreCase));

        var sqlClientActivity = activities.FirstOrDefault(activity =>
            activity.Source.Name.Contains("SqlClient", StringComparison.OrdinalIgnoreCase)
            || activity.OperationName.Contains("SqlClient", StringComparison.OrdinalIgnoreCase));

        httpServerActivity.Should().NotBeNull(
            "an HTTP-server activity must exist for the request (ASP.NET Core creates one for " +
            "every incoming request regardless of instrumentation wiring; captured " +
            $"activities were: [{string.Join(", ", activities.Select(a => $"{a.Source.Name}/{a.OperationName}"))}]).");

        sqlClientActivity.Should().NotBeNull(
            "the request touches the database (GetTenant reads via EF Core/SqlClient), so a " +
            "SQL-client activity must exist — this is the piece T019's SqlClient " +
            $"instrumentation is responsible for; captured activities were: " +
            $"[{string.Join(", ", activities.Select(a => $"{a.Source.Name}/{a.OperationName}"))}].");

        sqlClientActivity!.TraceId.Should().Be(
            httpServerActivity!.TraceId,
            "the HTTP-server activity and the SQL-client activity for one request must share a " +
            "single TraceId to form one connected trace — this is the property T019's " +
            "instrumentation wiring produces.");
    }

    /// <summary>
    /// T016: the structured log line for a request must carry the same <c>TraceId</c> as its
    /// corresponding span/activity. Uses <see cref="ApiFactory.CapturedLogMessages"/> (T053's
    /// existing log-capture mechanism) alongside an <see cref="ActivityListener"/> capturing the
    /// request's HTTP-server activity.
    /// </summary>
    [Fact]
    public async Task GetTenant_LogLine_CarriesSameTraceId_AsItsActivity()
    {
        await Factory.InitializeDatabaseAsync();
        var seed = await Factory.SeedTwoTenantsAsync();

        var capturedActivities = new System.Collections.Concurrent.ConcurrentQueue<Activity>();

        using var listener = new ActivityListener
        {
            ShouldListenTo = _ => true,
            Sample = (ref ActivityCreationOptions<ActivityContext> _) =>
                ActivitySamplingResult.AllDataAndRecorded,
            ActivityStopped = capturedActivities.Enqueue,
        };
        ActivitySource.AddActivityListener(listener);

        Factory.ClearCapturedLogs();

        using var client = Factory.CreateClient();
        using var request = new HttpRequestMessage(
            HttpMethod.Get,
            $"/tenants/{seed.TenantA.TenantId.Value}");
        request.Headers.Authorization = new AuthenticationHeaderValue("TestScheme", "test");
        request.Headers.Add("X-Test-Oid", seed.TenantA.EntraObjectId.ToString());
        request.Headers.Add("X-Test-Tid", seed.TenantA.EntraTenantId.ToString());

        var response = await client.SendAsync(request, TestContext.Current.CancellationToken);
        response.EnsureSuccessStatusCode();

        var activities = capturedActivities.ToArray();
        var httpServerActivity = activities.FirstOrDefault(activity =>
            activity.Kind == ActivityKind.Server
            || activity.OperationName.Contains("Microsoft.AspNetCore", StringComparison.OrdinalIgnoreCase)
            || activity.DisplayName.Contains("HTTP GET", StringComparison.OrdinalIgnoreCase));

        httpServerActivity.Should().NotBeNull(
            "an HTTP-server activity must exist for the request before a log-correlation " +
            "assertion can even be attempted.");

        var traceId = httpServerActivity!.TraceId.ToHexString();
        var capturedLogs = Factory.CapturedLogMessages;

        capturedLogs.Should().NotBeEmpty(
            "the request must produce at least one captured log line to check for trace " +
            "correlation.");

        capturedLogs.Should().Contain(
            message => message.Contains(traceId, StringComparison.OrdinalIgnoreCase),
            "the structured log line for this request must carry the same TraceId " +
            $"({traceId}) as its corresponding HTTP-server activity — this is what T019-T021's " +
            "OpenTelemetry logging wiring (trace-context-aware log formatting/enrichment) is " +
            "responsible for producing. Captured log messages were: " +
            $"[{string.Join(" | ", capturedLogs)}].");
    }
}
