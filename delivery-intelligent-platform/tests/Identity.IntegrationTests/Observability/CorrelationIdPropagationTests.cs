using System.Diagnostics;
using System.Net.Http.Headers;
using AwesomeAssertions;
using Identity.Domain.Abstractions;
using Identity.IntegrationTests.Infrastructure;
using Xunit;

namespace Identity.IntegrationTests.Observability;

/// <summary>
/// Verifies that ASP.NET Core/SqlClient OpenTelemetry auto-instrumentation, wired into
/// <c>AddIdentityObservability</c> (see <c>OpenTelemetryExtensions</c>), correctly correlates
/// activities and log lines for a single request.
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
/// <b>What the trace-connectivity assertion depends on.</b> The
/// correctness property under test is "the HTTP-server activity and the SQL-client activity for
/// one request share a single <c>TraceId</c>" — trace *connectivity*, not merely that either
/// activity individually exists. ASP.NET Core's hosting <see cref="Activity"/> establishes the
/// root of the trace for the request; whether SqlClient's own <see cref="Activity"/> is created
/// as a *child* of that same trace (sharing its <c>TraceId</c>) depends on
/// <see cref="Activity.Current"/> flowing correctly through the async call chain from the
/// controller/endpoint into the EF Core/SqlClient call — something the .NET runtime's ambient
/// <see cref="Activity.Current"/> propagation generally does on its own via
/// <see cref="System.Threading.ExecutionContext"/>, with no OpenTelemetry involvement at all. This
/// TraceId-sharing assertion is therefore reinforced by both the runtime's ambient activity
/// propagation and OpenTelemetry's own
/// AddAspNetCoreInstrumentation/AddSqlClientInstrumentation packages.
/// </para>
/// </remarks>
public sealed class CorrelationIdPropagationTests : IdentityIntegrationTestBase
{
    public CorrelationIdPropagationTests(SqlServerFixture sqlServerFixture, ApiFactory factory)
        : base(sqlServerFixture, factory)
    {
    }

    /// <summary>
    /// A request that touches the database (<c>GET /members</c>, an existing
    /// endpoint from spec 001/002) must produce one connected trace — at least one HTTP-server
    /// activity and at least one SQL-client activity, all sharing the same <c>TraceId</c>.
    /// </summary>
    [Fact]
    public async Task GetMembers_ProducesOneConnectedTrace_AcrossHttpAndSqlActivities()
    {
        await Factory.InitializeDatabaseAsync();
        var seed = await Factory.SeedMemberAsync(Role.Administrator);

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
            "/members");
        request.Headers.Authorization = new AuthenticationHeaderValue("TestScheme", "test");
        request.Headers.Add("X-Test-Oid", seed.EntraObjectId.ToString());
        request.Headers.Add("X-Test-Tid", seed.EntraTenantId.ToString());

        var response = await client.SendAsync(request, TestContext.Current.CancellationToken);
        response.EnsureSuccessStatusCode();
        // Drain the response body: ASP.NET Core's HttpRequestIn activity only fires
        // ActivityStopped once the response has been fully read. Draining alone isn't
        // quite enough — the activity is stopped slightly after the response stream
        // completes, on the server-side request-processing continuation — so poll
        // briefly for it rather than asserting immediately.
        _ = await response.Content.ReadAsStringAsync(TestContext.Current.CancellationToken);

        Activity[] activities = [];
        for (var attempt = 0; attempt < 20; attempt++)
        {
            activities = capturedActivities.ToArray();
            if (activities.Any(activity =>
                activity.Kind == ActivityKind.Server
                || activity.OperationName.Contains("Microsoft.AspNetCore", StringComparison.OrdinalIgnoreCase)
                || activity.DisplayName.Contains("HTTP GET", StringComparison.OrdinalIgnoreCase)))
            {
                break;
            }

            await Task.Delay(50, TestContext.Current.CancellationToken);
        }

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
            "the request touches the database (GET /members reads via EF Core/SqlClient), so a " +
            "SQL-client activity must exist — this is the piece the SqlClient " +
            $"instrumentation is responsible for; captured activities were: " +
            $"[{string.Join(", ", activities.Select(a => $"{a.Source.Name}/{a.OperationName}"))}].");

        sqlClientActivity!.TraceId.Should().Be(
            httpServerActivity!.TraceId,
            "the HTTP-server activity and the SQL-client activity for one request must share a " +
            "single TraceId to form one connected trace — this is the property the " +
            "instrumentation wiring produces.");

        // Identity enrichment on the span (FR-004, ADR-025 decision 7): the request's server
        // span carries user.id, and no span carries a tenant attribute.
        httpServerActivity.GetTagItem("user.id").Should().Be(seed.EntraObjectId.ToString());
        activities.Should().NotContain(activity => activity.GetTagItem("tenant.id") != null);
    }

    /// <summary>
    /// The structured log line for a request must carry the same <c>TraceId</c> as its
    /// corresponding span/activity. Uses <see cref="ApiFactory.CapturedLogMessages"/> (the
    /// log-capture mechanism) alongside an <see cref="ActivityListener"/> capturing the
    /// request's HTTP-server activity.
    /// </summary>
    [Fact]
    public async Task GetMembers_LogLine_CarriesSameTraceId_AsItsActivity()
    {
        await Factory.InitializeDatabaseAsync();
        var seed = await Factory.SeedMemberAsync(Role.Administrator);

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
            "/members");
        request.Headers.Authorization = new AuthenticationHeaderValue("TestScheme", "test");
        request.Headers.Add("X-Test-Oid", seed.EntraObjectId.ToString());
        request.Headers.Add("X-Test-Tid", seed.EntraTenantId.ToString());

        var response = await client.SendAsync(request, TestContext.Current.CancellationToken);
        response.EnsureSuccessStatusCode();
        // Drain the response body: ASP.NET Core's HttpRequestIn activity only fires
        // ActivityStopped once the response has been fully read. Draining alone isn't
        // quite enough — the activity is stopped slightly after the response stream
        // completes, on the server-side request-processing continuation — so poll
        // briefly for it rather than asserting immediately.
        _ = await response.Content.ReadAsStringAsync(TestContext.Current.CancellationToken);

        Activity[] activities = [];
        for (var attempt = 0; attempt < 20; attempt++)
        {
            activities = capturedActivities.ToArray();
            if (activities.Any(activity =>
                activity.Kind == ActivityKind.Server
                || activity.OperationName.Contains("Microsoft.AspNetCore", StringComparison.OrdinalIgnoreCase)
                || activity.DisplayName.Contains("HTTP GET", StringComparison.OrdinalIgnoreCase)))
            {
                break;
            }

            await Task.Delay(50, TestContext.Current.CancellationToken);
        }

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
            $"({traceId}) as its corresponding HTTP-server activity — this is what the " +
            "OpenTelemetry logging wiring (trace-context-aware log formatting/enrichment) is " +
            "responsible for producing. Captured log messages were: " +
            $"[{string.Join(" | ", capturedLogs)}].");
    }

    /// <summary>
    /// A request bearing a malformed <c>traceparent</c> header must not have that value
    /// adopted or propagated, and must not fail — ASP.NET Core's built-in W3C Trace Context
    /// propagator (the default <see cref="System.Diagnostics.DistributedContextPropagator"/>)
    /// discards malformed input and generates a fresh, valid <c>TraceId</c> for the request's
    /// root activity instead. This is FR-001's "generate fresh otherwise" half and the spec's
    /// malformed-correlation-ID edge case.
    /// </summary>
    [Fact]
    public async Task GetMembers_WithMalformedTraceparentHeader_GeneratesFreshValidTraceId()
    {
        await Factory.InitializeDatabaseAsync();
        var seed = await Factory.SeedMemberAsync(Role.Administrator);

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
            "/members");
        request.Headers.Authorization = new AuthenticationHeaderValue("TestScheme", "test");
        request.Headers.Add("X-Test-Oid", seed.EntraObjectId.ToString());
        request.Headers.Add("X-Test-Tid", seed.EntraTenantId.ToString());
        request.Headers.Add("traceparent", "not-a-valid-traceparent");

        var response = await client.SendAsync(request, TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(
            System.Net.HttpStatusCode.OK,
            "a malformed traceparent header must not cause the request to be rejected or " +
            "fail — it should simply be discarded in favor of a freshly generated trace ID.");

        // Drain the response body: ASP.NET Core's HttpRequestIn activity only fires
        // ActivityStopped once the response has been fully read. Draining alone isn't
        // quite enough — the activity is stopped slightly after the response stream
        // completes, on the server-side request-processing continuation — so poll
        // briefly for it rather than asserting immediately.
        _ = await response.Content.ReadAsStringAsync(TestContext.Current.CancellationToken);

        Activity[] activities = [];
        for (var attempt = 0; attempt < 20; attempt++)
        {
            activities = capturedActivities.ToArray();
            if (activities.Any(activity =>
                activity.Kind == ActivityKind.Server
                || activity.OperationName.Contains("Microsoft.AspNetCore", StringComparison.OrdinalIgnoreCase)
                || activity.DisplayName.Contains("HTTP GET", StringComparison.OrdinalIgnoreCase)))
            {
                break;
            }

            await Task.Delay(50, TestContext.Current.CancellationToken);
        }

        var httpServerActivity = activities.FirstOrDefault(activity =>
            activity.Kind == ActivityKind.Server
            || activity.OperationName.Contains("Microsoft.AspNetCore", StringComparison.OrdinalIgnoreCase)
            || activity.DisplayName.Contains("HTTP GET", StringComparison.OrdinalIgnoreCase));

        httpServerActivity.Should().NotBeNull(
            "an HTTP-server activity must exist for the request even when the incoming " +
            "traceparent header is malformed.");

        httpServerActivity!.TraceId.Should().NotBe(
            default(ActivityTraceId),
            "the server must generate a fresh, valid TraceId when the incoming header is " +
            "malformed, rather than leaving it unset.");

        var malformedValueAsHex = "not-a-valid-traceparent".Replace("-", string.Empty);
        httpServerActivity.TraceId.ToHexString().Should().NotBe(
            malformedValueAsHex,
            "the malformed header's content must not be adopted verbatim as the TraceId — " +
            "it must be discarded, not propagated.");
    }

    /// <summary>
    /// A request bearing a well-formed <c>traceparent</c> header must have its TraceId
    /// adopted by the server's root activity — proving the "propagate if valid" half of FR-001,
    /// complementing the malformed-header test above.
    /// </summary>
    [Fact]
    public async Task GetMembers_WithWellFormedTraceparentHeader_AdoptsSameTraceId()
    {
        await Factory.InitializeDatabaseAsync();
        var seed = await Factory.SeedMemberAsync(Role.Administrator);

        var capturedActivities = new System.Collections.Concurrent.ConcurrentQueue<Activity>();

        using var listener = new ActivityListener
        {
            ShouldListenTo = _ => true,
            Sample = (ref ActivityCreationOptions<ActivityContext> _) =>
                ActivitySamplingResult.AllDataAndRecorded,
            ActivityStopped = capturedActivities.Enqueue,
        };
        ActivitySource.AddActivityListener(listener);

        var expectedTraceId = ActivityTraceId.CreateRandom().ToHexString();
        var expectedSpanId = ActivitySpanId.CreateRandom().ToHexString();
        var traceparentValue = $"00-{expectedTraceId}-{expectedSpanId}-01";

        using var client = Factory.CreateClient();
        using var request = new HttpRequestMessage(
            HttpMethod.Get,
            "/members");
        request.Headers.Authorization = new AuthenticationHeaderValue("TestScheme", "test");
        request.Headers.Add("X-Test-Oid", seed.EntraObjectId.ToString());
        request.Headers.Add("X-Test-Tid", seed.EntraTenantId.ToString());
        request.Headers.Add("traceparent", traceparentValue);

        var response = await client.SendAsync(request, TestContext.Current.CancellationToken);
        response.EnsureSuccessStatusCode();
        // Drain the response body: ASP.NET Core's HttpRequestIn activity only fires
        // ActivityStopped once the response has been fully read. Draining alone isn't
        // quite enough — the activity is stopped slightly after the response stream
        // completes, on the server-side request-processing continuation — so poll
        // briefly for it rather than asserting immediately.
        _ = await response.Content.ReadAsStringAsync(TestContext.Current.CancellationToken);

        Activity[] activities = [];
        for (var attempt = 0; attempt < 20; attempt++)
        {
            activities = capturedActivities.ToArray();
            if (activities.Any(activity =>
                activity.Kind == ActivityKind.Server
                || activity.OperationName.Contains("Microsoft.AspNetCore", StringComparison.OrdinalIgnoreCase)
                || activity.DisplayName.Contains("HTTP GET", StringComparison.OrdinalIgnoreCase)))
            {
                break;
            }

            await Task.Delay(50, TestContext.Current.CancellationToken);
        }

        var httpServerActivity = activities.FirstOrDefault(activity =>
            activity.Kind == ActivityKind.Server
            || activity.OperationName.Contains("Microsoft.AspNetCore", StringComparison.OrdinalIgnoreCase)
            || activity.DisplayName.Contains("HTTP GET", StringComparison.OrdinalIgnoreCase));

        httpServerActivity.Should().NotBeNull(
            "an HTTP-server activity must exist for the request when a well-formed " +
            "traceparent header is supplied.");

        httpServerActivity!.TraceId.ToHexString().Should().Be(
            expectedTraceId,
            "a well-formed incoming traceparent header's TraceId must be adopted by the " +
            "server's root activity — this is the 'propagate if valid' half of FR-001, " +
            $"proving W3C Trace Context propagation is in effect (traceparent sent: " +
            $"{traceparentValue}).");
    }
}
