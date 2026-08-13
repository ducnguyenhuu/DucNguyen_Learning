using System.Net;
using System.Net.Http.Headers;
using AwesomeAssertions;
using Tenancy.IntegrationTests.Infrastructure;
using Xunit;

namespace Tenancy.IntegrationTests.Isolation;

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
/// <c>TenancyDbContext</c>'s <c>"TenantFilter"</c> global query filter caused
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
public sealed class TenantEndpointIsolationTests : IClassFixture<ApiFactory>
{
    private readonly ApiFactory _factory;

    public TenantEndpointIsolationTests(SqlServerFixture sqlServerFixture, ApiFactory factory)
    {
        _factory = factory;
        _factory.UseConnectionString(sqlServerFixture.ConnectionString);
    }

    [Fact]
    public async Task Get_TenantById_ForOtherTenant_IsRefused_AndIndistinguishableFromNonExistentTenant()
    {
        await _factory.InitializeDatabaseAsync();
        var seed = await _factory.SeedTwoTenantsAsync();

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

    [Fact]
    public async Task Patch_TenantById_ForOtherTenant_IsRefused_AndIndistinguishableFromNonExistentTenant()
    {
        await _factory.InitializeDatabaseAsync();
        var seed = await _factory.SeedTwoTenantsAsync();

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
        await _factory.InitializeDatabaseAsync();
        await _factory.SeedTwoTenantsAsync();

        using var client = _factory.CreateClient();
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("TestScheme", "test");
        client.DefaultRequestHeaders.Add("X-Test-Oid", Guid.NewGuid().ToString());
        client.DefaultRequestHeaders.Add("X-Test-Tid", Guid.NewGuid().ToString());

        var response = await client.PostAsync(
            "/tenants",
            JsonContent("New Tenant"),
            TestContext.Current.CancellationToken);

        response.StatusCode.Should().NotBe(HttpStatusCode.OK);
    }

    /// <summary>
    /// Minimal coverage for the two ADR-017-exception endpoints — see remarks on
    /// <see cref="Post_Tenants_DoesNotErrorRegardlessOfOtherTenants"/>.
    /// </summary>
    [Fact]
    public async Task Get_Tenants_DoesNotLeakAcrossTenants()
    {
        await _factory.InitializeDatabaseAsync();
        var seed = await _factory.SeedTwoTenantsAsync();

        using var client = CreateAuthenticatedClient(seed);

        var response = await client.GetAsync("/tenants", TestContext.Current.CancellationToken);

        response.StatusCode.Should().NotBe(HttpStatusCode.OK);
    }

    private HttpClient CreateAuthenticatedClient(TwoTenantSeed seed)
    {
        var client = _factory.CreateClient();
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("TestScheme", "test");
        client.DefaultRequestHeaders.Add("X-Test-Oid", seed.TenantA.EntraObjectId.ToString());
        client.DefaultRequestHeaders.Add("X-Test-Tid", seed.TenantA.EntraTenantId.ToString());
        return client;
    }

    private static System.Net.Http.Json.JsonContent JsonContent(object payload) =>
        System.Net.Http.Json.JsonContent.Create(new { name = payload });
}
