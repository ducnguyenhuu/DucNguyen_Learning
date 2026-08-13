using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using AwesomeAssertions;
using Tenancy.IntegrationTests.Infrastructure;
using Xunit;

namespace Tenancy.IntegrationTests.Scenarios;

/// <summary>
/// Failing acceptance-scenario tests (T045) for US1's five acceptance scenarios (spec.md).
/// </summary>
/// <remarks>
/// <b>What this file proves right now, and what it doesn't.</b> Same caveat as T043/T044's
/// isolation tests: none of the <c>/tenants</c> endpoints exist yet (T058 adds them), so every
/// request below either hits a route absent from <c>Program.cs</c>'s route table, or (for the
/// unauthenticated scenario) is rejected by the auth pipeline before routing even matters. These
/// tests are expected to be red (or green for the wrong reason) today; they encode the
/// eventual-correct behavior per spec.md so they'll go genuinely green once T058 lands the
/// endpoints.
/// </remarks>
public sealed class EstablishTenantTests : IClassFixture<ApiFactory>
{
    private readonly ApiFactory _factory;

    public EstablishTenantTests(SqlServerFixture sqlServerFixture, ApiFactory factory)
    {
        _factory = factory;
        _factory.UseConnectionString(sqlServerFixture.ConnectionString);
    }

    /// <summary>
    /// Scenario 1: an authenticated user with no tenant creates one via a valid display name;
    /// the tenant is persisted with a unique id, the creator recorded as its administrator, and
    /// the tenant's details returned to the caller.
    /// </summary>
    [Fact]
    public async Task Post_Tenants_WithValidDisplayName_CreatesTenant_AndReturnsItToCaller()
    {
        await _factory.InitializeDatabaseAsync();

        using var client = _factory.CreateClient();
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("TestScheme", "test");
        client.DefaultRequestHeaders.Add("X-Test-Oid", Guid.NewGuid().ToString());
        client.DefaultRequestHeaders.Add("X-Test-Tid", Guid.NewGuid().ToString());
        client.DefaultRequestHeaders.Add("Idempotency-Key", Guid.NewGuid().ToString());

        var response = await client.PostAsync(
            "/tenants",
            JsonContent("Acme Delivery Co"),
            TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.Created);
    }

    /// <summary>
    /// Scenario 2: an authenticated administrator of Tenant A requests Tenant B by id and is
    /// refused, with the response revealing nothing about whether Tenant B exists. This overlaps
    /// T044's exhaustive isolation coverage; one straightforward assertion suffices here.
    /// </summary>
    [Fact]
    public async Task Get_TenantById_ForOtherTenant_IsRefused()
    {
        await _factory.InitializeDatabaseAsync();
        var seed = await _factory.SeedTwoTenantsAsync();

        using var client = CreateAuthenticatedClient(seed.TenantA);

        var response = await client.GetAsync(
            $"/tenants/{seed.TenantB.TenantId.Value}",
            TestContext.Current.CancellationToken);

        response.StatusCode.Should().NotBe(HttpStatusCode.OK);
    }

    /// <summary>
    /// Scenario 3: an authenticated administrator updates the tenant's display name to a valid
    /// value; the change is persisted and reflected in a subsequent read (PATCH then GET).
    /// </summary>
    /// <remarks>
    /// This can't meaningfully run yet — no tenant can be created via POST until T058 lands the
    /// endpoints — so this exercises the flow against a database-seeded tenant and is written as
    /// the eventual-correct-behavior spec. It's expected to fail for the same "route absent"
    /// reason as the other scenarios here.
    /// </remarks>
    [Fact]
    public async Task Patch_TenantDisplayName_ThenGet_ReflectsUpdatedName()
    {
        await _factory.InitializeDatabaseAsync();
        var seed = await _factory.SeedTwoTenantsAsync();

        using var client = CreateAuthenticatedClient(seed.TenantA);

        const string updatedName = "Renamed Tenant A";

        var initialGetResponse = await client.GetAsync(
            $"/tenants/{seed.TenantA.TenantId.Value}",
            TestContext.Current.CancellationToken);
        initialGetResponse.StatusCode.Should().Be(HttpStatusCode.OK);
        var etag = initialGetResponse.Headers.ETag;
        etag.Should().NotBeNull();

        using var patchRequest = new HttpRequestMessage(HttpMethod.Patch, $"/tenants/{seed.TenantA.TenantId.Value}")
        {
            Content = JsonContent(updatedName),
        };
        patchRequest.Headers.IfMatch.Add(etag!);

        var patchResponse = await client.SendAsync(patchRequest, TestContext.Current.CancellationToken);

        patchResponse.StatusCode.Should().Be(HttpStatusCode.OK);

        var getResponse = await client.GetAsync(
            $"/tenants/{seed.TenantA.TenantId.Value}",
            TestContext.Current.CancellationToken);

        getResponse.StatusCode.Should().Be(HttpStatusCode.OK);

        var body = await getResponse.Content.ReadAsStringAsync(TestContext.Current.CancellationToken);
        body.Should().Contain(updatedName);
    }

    /// <summary>
    /// Scenario 4: an unauthenticated caller attempts a tenant operation and is rejected as
    /// unauthenticated, with no tenant data disclosed. Overlaps T046's exhaustive 401 coverage;
    /// one representative case is enough here.
    /// </summary>
    [Fact]
    public async Task Get_Tenants_WithoutAuthentication_IsRejectedAsUnauthenticated()
    {
        await _factory.InitializeDatabaseAsync();

        using var client = _factory.CreateClient();

        var response = await client.GetAsync("/tenants", TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.Unauthorized);

        var body = await response.Content.ReadAsStringAsync(TestContext.Current.CancellationToken);
        body.Should().NotContain("Tenant");
    }

    /// <summary>
    /// Scenario 5: an authenticated user lists tenants and sees only tenants they're a member
    /// of. Overlaps T048's exhaustive ADR-017-exception coverage; one straightforward case is
    /// enough here.
    /// </summary>
    [Fact]
    public async Task Get_Tenants_ForAuthenticatedUser_ReturnsOnlyTenantsTheyAreMemberOf()
    {
        await _factory.InitializeDatabaseAsync();
        var seed = await _factory.SeedTwoTenantsAsync();

        using var client = CreateAuthenticatedClient(seed.TenantA);

        var response = await client.GetAsync("/tenants", TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.OK);

        var body = await response.Content.ReadAsStringAsync(TestContext.Current.CancellationToken);
        body.Should().Contain(seed.TenantA.TenantId.Value.ToString());
        body.Should().NotContain(seed.TenantB.TenantId.Value.ToString());
    }

    private HttpClient CreateAuthenticatedClient(SeededTenant seededTenant)
    {
        var client = _factory.CreateClient();
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("TestScheme", "test");
        client.DefaultRequestHeaders.Add("X-Test-Oid", seededTenant.EntraObjectId.ToString());
        client.DefaultRequestHeaders.Add("X-Test-Tid", seededTenant.EntraTenantId.ToString());
        return client;
    }

    private static JsonContent JsonContent(object payload) =>
        System.Net.Http.Json.JsonContent.Create(new { displayName = payload });
}
