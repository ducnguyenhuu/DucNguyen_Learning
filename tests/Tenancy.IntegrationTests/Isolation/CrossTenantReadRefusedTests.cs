using System.Net;
using System.Net.Http.Headers;
using AwesomeAssertions;
using Tenancy.IntegrationTests.Infrastructure;
using Xunit;

namespace Tenancy.IntegrationTests.Isolation;

/// <summary>
/// First cross-tenant isolation test (T043). Authenticates as Tenant A's member (via T040's
/// <see cref="TestAuthHandler"/>) and attempts to read a resource scoped to Tenant B.
/// </summary>
/// <remarks>
/// <b>What this test proves right now, and what it doesn't.</b> No tenant-scoped endpoints exist
/// yet (Phase 3+ adds them), so the request below hits a route that simply does not exist in
/// <c>Program.cs</c>'s route table. The plain ASP.NET Core "no matching endpoint" 404 asserted
/// here is a routing-table fact, not an isolation-check fact — it would look identical whether
/// or not tenant isolation were ever implemented correctly. This red only proves the route is
/// absent. T060 (after Phase 3 adds the real <c>/tenants/{tenantId}/memberships</c> endpoint) is
/// the task that turns this into a real assertion: first confirming the *same* 404 now comes from
/// a membership check rather than a missing route, then deliberately re-breaking isolation to
/// confirm this test actually catches a real cross-tenant leak. Until T060 lands, treat this test
/// as scaffolding, not as isolation coverage.
/// </remarks>
public sealed class CrossTenantReadRefusedTests : IClassFixture<ApiFactory>
{
    private readonly ApiFactory _factory;

    public CrossTenantReadRefusedTests(SqlServerFixture sqlServerFixture, ApiFactory factory)
    {
        _factory = factory;
        _factory.UseConnectionString(sqlServerFixture.ConnectionString);
    }

    [Fact]
    public async Task Get_MembershipsForOtherTenant_IsRefused()
    {
        // Arrange: apply migrations and seed two independent tenants (T042).
        await _factory.InitializeDatabaseAsync();
        var seed = await _factory.SeedTwoTenantsAsync();

        using var client = _factory.CreateClient();

        // Authenticate as Tenant A's member via T040's header-driven TestAuthHandler. A bare,
        // non-empty Authorization header is required to enter TestAuthHandler's "caller is
        // claiming this scheme" branch; its exact value is irrelevant since TestAuthHandler
        // reads X-Test-Oid/X-Test-Tid instead of parsing the Authorization header itself. It must
        // not start with "Bearer " though, or ApiFactory's PolicyScheme selector would forward the
        // request to the real JwtBearer handler instead.
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("TestScheme", "test");
        client.DefaultRequestHeaders.Add("X-Test-Oid", seed.TenantA.EntraObjectId.ToString());
        client.DefaultRequestHeaders.Add("X-Test-Tid", seed.TenantA.EntraTenantId.ToString());

        // Act: Tenant A's member attempts to read Tenant B's memberships.
        var response = await client.GetAsync(
            $"/tenants/{seed.TenantB.TenantId.Value}/memberships",
            TestContext.Current.CancellationToken);

        // Assert: not a 200 (would mean the leak happened), and specifically not a 403 either
        // (per ADR-017, tenant isolation should look like "doesn't exist," not "exists but
        // forbidden" — a 403 would leak the resource's existence across tenant boundaries).
        // Today, with no route registered at all, this resolves as a plain "no matching
        // endpoint" 404 from ASP.NET Core's routing middleware — that is the only kind of 404
        // possible right now, since no [HttpGet] for this path exists in Program.cs yet.
        //
        // NOTE for T060: once the real endpoint exists, this exact assertion (status == 404)
        // will still pass, but for a completely different reason (a membership-scoped query
        // returning "not found" for a tenant the caller isn't a member of) — same status code,
        // different cause. T060 must additionally prove the *cause* has changed, e.g. by first
        // asserting this 404 survives once the route exists, then deliberately breaking the
        // membership check and confirming the test starts failing (turns green->red on a real
        // leak) before restoring it.
        response.StatusCode.Should().Be(HttpStatusCode.NotFound);
        response.StatusCode.Should().NotBe(HttpStatusCode.OK);
        response.StatusCode.Should().NotBe(HttpStatusCode.Forbidden);
    }
}
