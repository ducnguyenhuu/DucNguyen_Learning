using System.Net;
using System.Net.Http.Headers;
using ArchitectureTests.Support;
using AwesomeAssertions;
using Identity.IntegrationTests.Infrastructure;
using Xunit;

namespace Identity.IntegrationTests.Isolation;

/// <summary>
/// Failing isolation tests (T044) for all four tenant endpoints
/// (<c>POST /tenants</c>, <c>GET /tenants</c>, <c>GET /tenants/{tenantId}</c>,
/// <c>PATCH /tenants/{tenantId}</c>).
/// </summary>
/// <remarks>
/// <b>What this file proves, and how it was proven (T060).</b> All four endpoints now exist
/// (T058/T059). T060 confirmed that <see cref="Get_TenantById_ForOtherTenant_IsRefused_AndIndistinguishableFromNonExistentTenant"/>'s
/// (and, secondarily, <see cref="Patch_TenantById_ForOtherTenant_IsRefused_AndIndistinguishableFromNonExistentTenant"/>'s)
/// 404 comes from a genuine membership check, not a missing route: temporarily disabling
/// <c>IdentityDbContext</c>'s <c>"TenantFilter"</c> global query filter caused
/// <c>Get_TenantById...</c> to fail with an actual <c>HttpStatusCode.OK</c> (200) carrying Tenant
/// B's real <c>displayName</c> — traced via the EF Core command log to
/// <c>TenantContextResolutionMiddleware</c>'s unscoped <c>Memberships</c> lookup incorrectly
/// treating the caller's own (real, but wrong-tenant) active membership as valid for Tenant B —
/// and <c>Patch_TenantById...</c> to fail with <c>428 PreconditionRequired</c> instead of 404
/// (i.e. it also reached real per-tenant mutation logic against Tenant B's actual record).
/// Restoring the filter returned both to green. See
/// <c>.superpowers/sdd/tasks/task-60-report.md</c> for the full literal before/during/after test
/// output. This is what distinguishes this suite from scaffolding that merely detects an absent
/// route.
/// </remarks>
public sealed class TenantEndpointIsolationTests : IdentityIntegrationTestBase
{

    public TenantEndpointIsolationTests(SqlServerFixture sqlServerFixture, ApiFactory factory)
        : base(sqlServerFixture, factory)
    {
    }

    [CoversRequirement("FR-007")]
    [CoversRequirement("FR-008")]
    [CoversRequirement("FR-009")]
    [Fact]
    public async Task Get_TenantById_ForOtherTenant_IsRefused_AndIndistinguishableFromNonExistentTenant()
    {
        await Factory.InitializeDatabaseAsync();
        var seed = await Factory.SeedTwoTenantsAsync();

        using var client = CreateAuthenticatedClient(seed);

        // Wrong-tenant case: Tenant A's member requests Tenant B's tenant record.
        var wrongTenantResponse = await client.GetAsync(
            $"/tenants/{seed.TenantB.TenantId.Value}",
            TestContext.Current.CancellationToken);

        // Non-existent-tenant case: a syntactically valid GUID that was never seeded.
        var neverSeededTenantId = Guid.NewGuid();
        var nonExistentResponse = await client.GetAsync(
            $"/tenants/{neverSeededTenantId}",
            TestContext.Current.CancellationToken);

        // Assert: refusal, not a leak (not 200) and not a distinguishing 403 (per ADR-017,
        // cross-tenant access should look identical to "doesn't exist").
        wrongTenantResponse.StatusCode.Should().Be(HttpStatusCode.NotFound);
        wrongTenantResponse.StatusCode.Should().NotBe(HttpStatusCode.OK);
        wrongTenantResponse.StatusCode.Should().NotBe(HttpStatusCode.Forbidden);

        // Assert: indistinguishable from the never-seeded-GUID case (SC-004/FR-009) — same
        // status code and same (empty/absent) body shape.
        nonExistentResponse.StatusCode.Should().Be(wrongTenantResponse.StatusCode);

        var wrongTenantBody = await wrongTenantResponse.Content.ReadAsStringAsync(
            TestContext.Current.CancellationToken);
        var nonExistentBody = await nonExistentResponse.Content.ReadAsStringAsync(
            TestContext.Current.CancellationToken);
        wrongTenantBody.Should().Be(nonExistentBody);
    }

    [CoversRequirement("FR-007")]
    [CoversRequirement("FR-008")]
    [Fact]
    public async Task Patch_TenantById_ForOtherTenant_IsRefused_AndIndistinguishableFromNonExistentTenant()
    {
        await Factory.InitializeDatabaseAsync();
        var seed = await Factory.SeedTwoTenantsAsync();

        using var client = CreateAuthenticatedClient(seed);

        // Wrong-tenant case: Tenant A's member attempts to patch Tenant B's tenant record.
        var wrongTenantResponse = await client.PatchAsync(
            $"/tenants/{seed.TenantB.TenantId.Value}",
            JsonContent("Attempted Rename"),
            TestContext.Current.CancellationToken);

        // Non-existent-tenant case: a syntactically valid GUID that was never seeded.
        var neverSeededTenantId = Guid.NewGuid();
        var nonExistentResponse = await client.PatchAsync(
            $"/tenants/{neverSeededTenantId}",
            JsonContent("Attempted Rename"),
            TestContext.Current.CancellationToken);

        wrongTenantResponse.StatusCode.Should().Be(HttpStatusCode.NotFound);
        wrongTenantResponse.StatusCode.Should().NotBe(HttpStatusCode.OK);
        wrongTenantResponse.StatusCode.Should().NotBe(HttpStatusCode.Forbidden);

        nonExistentResponse.StatusCode.Should().Be(wrongTenantResponse.StatusCode);

        var wrongTenantResponseBody = await wrongTenantResponse.Content.ReadAsStringAsync(
            TestContext.Current.CancellationToken);
        var nonExistentResponseBody = await nonExistentResponse.Content.ReadAsStringAsync(
            TestContext.Current.CancellationToken);
        wrongTenantResponseBody.Should().Be(nonExistentResponseBody);
    }

    /// <summary>
    /// Minimal coverage for the two ADR-017-exception endpoints (POST/GET-list are not
    /// tenant-scoped, so there's no isolation narrative to test — see task brief). Included
    /// only to satisfy "all four tenant endpoints"; T048 owns the real behavior of these two.
    /// </summary>
    [Fact]
    public async Task Post_Tenants_DoesNotErrorRegardlessOfOtherTenants()
    {
        await Factory.InitializeDatabaseAsync();
        await Factory.SeedTwoTenantsAsync();

        using var client = Factory.CreateClient();
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("TestScheme", "test");
        client.DefaultRequestHeaders.Add("X-Test-Oid", Guid.NewGuid().ToString());
        client.DefaultRequestHeaders.Add("X-Test-Tid", Guid.NewGuid().ToString());
        client.DefaultRequestHeaders.Add("Idempotency-Key", Guid.NewGuid().ToString());

        var response = await client.PostAsync(
            "/tenants",
            JsonContent("New Tenant"),
            TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.Created);
    }

    // Get_Tenants_DoesNotLeakAcrossTenants was removed here (T061): it asserted
    // `NotBe(HttpStatusCode.OK)` for a legitimate member's `GET /tenants`, contradicting
    // openapi.yaml's documented 200 for that case (`GET /tenants` is one of the two
    // deliberately unscoped, ADR-017-exception endpoints — a member listing their own
    // tenants is expected to succeed, not fail). Correcting the assertion to `200 OK` plus a
    // genuine isolation check (body contains Tenant A's data, not Tenant B's) would have made
    // this test a near-duplicate of two already-correct siblings:
    // <see cref="UnscopedOperationTests.Get_Tenants_ForTenantAMember_ReturnsOnlyTenantA_NotTenantB"/>
    // and
    // <see cref="Scenarios.MultiTenantMembershipTests.Get_Tenants_ForUserInBothTenants_ReturnsBothTenants_CorrectlySeparated"/>,
    // both of which already assert 200 plus the same "contains A, not B" body check against
    // the identical two-tenant seed. Rather than keep a third near-identical case, it was
    // deleted; the two siblings retain full coverage of this endpoint's isolation behavior.

    private HttpClient CreateAuthenticatedClient(TwoTenantSeed seed)
    {
        var client = Factory.CreateClient();
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("TestScheme", "test");
        client.DefaultRequestHeaders.Add("X-Test-Oid", seed.TenantA.EntraObjectId.ToString());
        client.DefaultRequestHeaders.Add("X-Test-Tid", seed.TenantA.EntraTenantId.ToString());
        return client;
    }

    private static System.Net.Http.Json.JsonContent JsonContent(object payload) =>
        System.Net.Http.Json.JsonContent.Create(new { displayName = payload });
}
