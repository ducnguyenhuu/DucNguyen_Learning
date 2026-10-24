using System.Net.Http.Headers;
using ArchitectureTests.Support;
using AwesomeAssertions;
using Identity.Domain.Abstractions;
using Identity.IntegrationTests.Infrastructure;
using Xunit;

namespace Identity.IntegrationTests.Scenarios;

/// <summary>
/// FR-025's hygiene half: whatever logging happens for an authenticated request — ASP.NET Core's
/// own request/hosting diagnostics, Microsoft.Identity.Web's logging, and this service's own
/// structured events — never leaks the bearer token, the raw <c>Authorization</c> header value,
/// or an obviously secret-shaped header value into a formatted log line. Uses
/// <see cref="ApiFactory.CapturedLogMessages"/> / <see cref="ApiFactory.ClearCapturedLogs"/>.
/// </summary>
/// <remarks>
/// <para>
/// <b>What this test does <em>not</em> cover.</b> Whether the structured business events FR-025
/// requires (membership changes, authorisation refusals) actually fire is
/// <see cref="LoggingCoverageTests"/>' job. This test is the tripwire for any logging call —
/// framework or ours — that dumps a credential or header verbatim.
/// </para>
/// <para>
/// <b>The secret-marker header check is a known limitation.</b> The custom
/// <c>X-Test-Fake-Secret</c> header injected below proves the logging pipeline doesn't blindly
/// dump arbitrary request headers wholesale — but nothing in this codebase today explicitly
/// redacts or allow-lists which headers get logged. This assertion currently passes because
/// ASP.NET Core's default request logging simply doesn't log raw header collections at the
/// default log level used in this test host, not because of any deliberate redaction logic
/// this project has built. That is a gap, not a guarantee — if request header logging is ever
/// added (e.g. for debugging), this test is the tripwire that should catch a naive
/// "log all headers" implementation, but it is not currently backed by a redaction mechanism
/// this project can point to.
/// </para>
/// </remarks>
public sealed class LogHygieneTests : IdentityIntegrationTestBase
{

    public LogHygieneTests(SqlServerFixture sqlServerFixture, ApiFactory factory)
        : base(sqlServerFixture, factory)
    {
    }

    /// <summary>
    /// Sends one authenticated, member-only request carrying a distinctive fake bearer token
    /// and a distinctive fake secret-shaped header, then asserts none of the captured log
    /// messages contain the token, the raw <c>Authorization</c> header value, or the fake
    /// secret marker.
    /// </summary>
    [CoversRequirement("FR-025")]
    [Fact]
    public async Task AuthenticatedRequest_NeverLogsBearerTokenOrSecretHeaderValues()
    {
        await Factory.InitializeDatabaseAsync();
        var seed = await Factory.SeedMemberAsync(Role.Administrator);

        // Deliberately distinctive, greppable fake values so a false negative (the assertion
        // passing only because the marker happens to collide with unrelated log text) is
        // implausible.
        const string fakeBearerToken =
            "LOGHYGIENE-T053-FAKE-BEARER-TOKEN-do-not-log-me-9f3a7c1e4b2d";
        const string fakeSecretHeaderValue =
            "LOGHYGIENE-T053-FAKE-SECRET-Server=fake;Password=do-not-log-me-8a1c2e9d";

        Factory.ClearCapturedLogs();

        using var client = Factory.CreateClient();
        using var request = new HttpRequestMessage(
            HttpMethod.Get,
            "/members");

        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", fakeBearerToken);
        request.Headers.Add("X-Test-Fake-Secret", fakeSecretHeaderValue);

        // Same request also authenticates as a seeded member via TestAuthHandler's headers
        // (T040) so the request completes a full authentication attempt rather than merely
        // hitting an anonymous 401 short-circuit — the Bearer-prefixed Authorization header
        // above routes to the real JwtBearer scheme per ApiFactory's PolicyScheme forwarding
        // rule (see ApiFactory's type-level remarks), which will fail signature validation
        // against this fake token; that failure path is exactly what must not log the token.
        request.Headers.Add("X-Test-Oid", seed.EntraObjectId.ToString());
        request.Headers.Add("X-Test-Tid", seed.EntraTenantId.ToString());

        await client.SendAsync(request, TestContext.Current.CancellationToken);

        var capturedLogs = Factory.CapturedLogMessages;

        capturedLogs.Should().NotBeEmpty(
            "ASP.NET Core's hosting/routing pipeline logs something for every request " +
            "regardless of outcome, so an empty capture would indicate the log-capture " +
            "mechanism itself is broken, not that the request was silent.");

        capturedLogs.Should().NotContain(
            message => message.Contains(fakeBearerToken, StringComparison.Ordinal),
            "the raw bearer token value must never appear in any log line.");

        var rawAuthorizationHeaderValue = $"Bearer {fakeBearerToken}";
        capturedLogs.Should().NotContain(
            message => message.Contains(rawAuthorizationHeaderValue, StringComparison.Ordinal),
            "the full Authorization header value must never appear verbatim in any log line.");

        capturedLogs.Should().NotContain(
            message => message.Contains(fakeSecretHeaderValue, StringComparison.Ordinal),
            "a secret-shaped custom header value must never appear verbatim in any log line " +
            "(see this test class's remarks for why this assertion is not yet backed by any " +
            "deliberate redaction mechanism in this codebase).");
    }
}
