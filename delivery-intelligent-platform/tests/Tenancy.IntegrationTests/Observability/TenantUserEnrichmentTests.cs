using System.Net.Http.Headers;
using AwesomeAssertions;
using Tenancy.IntegrationTests.Infrastructure;
using Xunit;

namespace Tenancy.IntegrationTests.Observability;

/// <summary>
/// FR-004's span/log enrichment with tenant and user identity
/// "when known at the point of emission." Two enrichment points exist at two different pipeline
/// depths — <see cref="Tenancy.Api.Middleware.UserIdentityEnrichmentMiddleware"/> (registered
/// right after <c>app.UseAuthentication()</c>, so it fires for every authenticated request) and
/// <see cref="Tenancy.Api.Middleware.TenantContextResolutionMiddleware"/>'s own enrichment
/// (added only once tenant membership is proven, and only for endpoints that opt into ADR-017's
/// resolution filter). These tests exercise both, plus the unauthenticated/exempt edge case
/// where only whatever identity is known (possibly none) gets attached — never a blocking
/// failure.
/// </summary>
public sealed class TenantUserEnrichmentTests : TenancyIntegrationTestBase
{
    public TenantUserEnrichmentTests(SqlServerFixture sqlServerFixture, ApiFactory factory)
        : base(sqlServerFixture, factory)
    {
    }

    /// <summary>
    /// An authenticated, tenant-scoped request (<c>GET /tenants/{tenantId}</c>, which opts into
    /// <c>WithTenantContextResolution()</c>) must produce a captured log line carrying both the
    /// caller's user id (from <see cref="Tenancy.Api.Middleware.UserIdentityEnrichmentMiddleware"/>,
    /// pushed before routing even resolves the endpoint) and the resolved tenant id (from
    /// <see cref="Tenancy.Api.Middleware.TenantContextResolutionMiddleware"/>'s own scope, nested
    /// inside the user-id scope) — proving both enrichment points fire together for a fully
    /// resolved request.
    /// </summary>
    [Fact]
    public async Task GetTenant_AuthenticatedAndTenantScoped_LogLine_CarriesBothUserIdAndTenantId()
    {
        await Factory.InitializeDatabaseAsync();
        var seed = await Factory.SeedTwoTenantsAsync();

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
        _ = await response.Content.ReadAsStringAsync(TestContext.Current.CancellationToken);

        var capturedLogs = Factory.CapturedLogMessages;
        var expectedUserId = seed.TenantA.EntraObjectId.ToString();
        var expectedTenantId = seed.TenantA.TenantId.Value.ToString();

        capturedLogs.Should().NotBeEmpty(
            "the request must produce at least one captured log line to check for identity " +
            "enrichment.");

        capturedLogs.Should().Contain(
            message => message.Contains($"UserId={expectedUserId}", StringComparison.OrdinalIgnoreCase)
                && message.Contains($"TenantId={expectedTenantId}", StringComparison.OrdinalIgnoreCase),
            "a fully resolved request (authenticated + tenant membership proven) must produce " +
            $"at least one log line carrying both UserId ({expectedUserId}) and TenantId " +
            $"({expectedTenantId}) in its active scopes — this is FR-004's tenant/user identity " +
            "enrichment. Captured log messages were: " +
            $"[{string.Join(" | ", capturedLogs)}].");
    }

    /// <summary>
    /// A request to one of ADR-017's three tenant-context-resolution-exempt operations
    /// (<c>GET /tenants</c> has no <c>{tenantId}</c> segment, so it never opts into
    /// <c>WithTenantContextResolution()</c>) still succeeds and still gets user-identity
    /// enrichment from <see cref="Tenancy.Api.Middleware.UserIdentityEnrichmentMiddleware"/> —
    /// tenant enrichment never runs for it, which is correct per FR-004's "when known," not a
    /// gap.
    /// </summary>
    [Fact]
    public async Task ListTenants_ExemptOperation_SucceedsAndCarriesUserId_WithNoTenantEnrichment()
    {
        await Factory.InitializeDatabaseAsync();
        var seed = await Factory.SeedTwoTenantsAsync();

        Factory.ClearCapturedLogs();

        using var client = Factory.CreateClient();
        using var request = new HttpRequestMessage(HttpMethod.Get, "/tenants");
        request.Headers.Authorization = new AuthenticationHeaderValue("TestScheme", "test");
        request.Headers.Add("X-Test-Oid", seed.TenantA.EntraObjectId.ToString());
        request.Headers.Add("X-Test-Tid", seed.TenantA.EntraTenantId.ToString());

        var response = await client.SendAsync(request, TestContext.Current.CancellationToken);

        response.IsSuccessStatusCode.Should().BeTrue(
            "an ADR-017-exempt operation must succeed without ever needing tenant context " +
            "enrichment to have happened.");

        _ = await response.Content.ReadAsStringAsync(TestContext.Current.CancellationToken);

        var capturedLogs = Factory.CapturedLogMessages;
        var expectedUserId = seed.TenantA.EntraObjectId.ToString();

        capturedLogs.Should().Contain(
            message => message.Contains($"UserId={expectedUserId}", StringComparison.OrdinalIgnoreCase),
            "user-identity enrichment must still apply to an exempt operation, since it is " +
            "known as soon as authentication runs, independent of tenant resolution. Captured " +
            $"log messages were: [{string.Join(" | ", capturedLogs)}].");

        capturedLogs.Should().NotContain(
            // A leading space distinguishes the "TenantId=" scope-dictionary key rendered by
            // CapturingLoggerProvider from unrelated substrings like EF Core's own
            // "@entraTenantId=" parameter-log text, which otherwise falsely contains "TenantId=".
            message => message.Contains(" TenantId=", StringComparison.OrdinalIgnoreCase),
            "an exempt operation never resolves a tenant context, so no log line should carry " +
            "a TenantId scope for this request.");
    }

    /// <summary>
    /// An unauthenticated request must not fail because identity enrichment has nothing to
    /// attach — per the spec's unauthenticated-caller edge case, enrichment happens with
    /// whatever context exists (none, here) and never blocks the request.
    /// </summary>
    [Fact]
    public async Task ListTenants_Unauthenticated_DoesNotFail()
    {
        await Factory.InitializeDatabaseAsync();
        await Factory.SeedTwoTenantsAsync();

        using var client = Factory.CreateClient();
        using var request = new HttpRequestMessage(HttpMethod.Get, "/tenants");
        // No Authorization header at all: TestAuthHandler.HandleAuthenticateAsync returns
        // NoResult() in this case, so the request reaches UserIdentityEnrichmentMiddleware with
        // no authenticated User — it must skip enrichment, not throw.

        var response = await client.SendAsync(request, TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(
            System.Net.HttpStatusCode.Unauthorized,
            "an unauthenticated request to an authorization-protected endpoint is correctly " +
            "rejected by UseAuthorization() — but critically, it must fail for that reason " +
            "alone, not because identity enrichment threw or otherwise malfunctioned when no " +
            "identity was present.");
    }
}
