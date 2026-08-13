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
/// <b>What this test proves right now, and what it doesn't.</b> The
/// <c>/tenants/{tenantId}/memberships</c> route this test targets does not exist yet in
/// <c>Program.cs</c>'s route table (a separate, later slice), so the 404 asserted here is still a
/// plain ASP.NET Core "no matching endpoint" routing-table fact, not an isolation-check fact — it
/// would look identical whether or not tenant isolation were ever implemented correctly. This test
/// therefore remains scaffolding, not isolation coverage, for this specific route. T060 has since
/// proven the isolation mechanism itself for the sibling <c>/tenants/{tenantId}</c> endpoint (see
/// <see cref="TenantEndpointIsolationTests.Get_TenantById_ForOtherTenant_IsRefused_AndIndistinguishableFromNonExistentTenant"/>):
/// disabling <c>TenancyDbContext</c>'s <c>"TenantFilter"</c> caused that test to fail with an
/// actual <c>200</c> returning Tenant B's real data (traced to
/// <c>TenantContextResolutionMiddleware</c>'s unscoped <c>Memberships</c> lookup incorrectly
/// resolving a caller's own membership as valid for a tenant they don't belong to), and restoring
/// the filter returned it to green — see <c>.superpowers/sdd/tasks/task-60-report.md</c> for the
/// literal before/during/after output. This test will get the same treatment once the
/// memberships endpoint exists.
/// </remarks>
public sealed class CrossTenantReadRefusedTests : TenancyIntegrationTestBase
{

    public CrossTenantReadRefusedTests(SqlServerFixture sqlServerFixture, ApiFactory factory)
        : base(sqlServerFixture, factory)
    {
    }

    [Fact]
    public async Task Get_MembershipsForOtherTenant_IsRefused()
    {
        // Arrange: apply migrations and seed two independent tenants (T042).
        await Factory.InitializeDatabaseAsync();
        var seed = await Factory.SeedTwoTenantsAsync();

        using var client = Factory.CreateClient();

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
