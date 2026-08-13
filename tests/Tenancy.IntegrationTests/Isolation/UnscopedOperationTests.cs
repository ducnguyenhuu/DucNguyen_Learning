using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using AwesomeAssertions;
using Tenancy.IntegrationTests.Infrastructure;
using Xunit;

namespace Tenancy.IntegrationTests.Isolation;

/// <summary>
/// Exhaustive, dedicated ADR-017-exception coverage for the two endpoints that are
/// deliberately unscoped by tenant: <c>POST /tenants</c> (no tenant context exists yet at
/// creation time) and <c>GET /tenants</c> (the one legitimate cross-tenant read in the whole
/// system, backed by T037's audited <c>MembershipDirectory</c>). Distinct from T044/T045's
/// lighter coverage of these same two endpoints in <see cref="TenantEndpointIsolationTests"/>
/// and <see cref="CrossTenantReadRefusedTests"/>.
/// </summary>
/// <remarks>
/// Neither endpoint exists yet (T058 adds them), so every request below currently hits a route
/// absent from <c>Program.cs</c>'s route table and gets a plain ASP.NET Core routing 404. These
/// tests are written as the target spec — <c>POST /tenants</c> should succeed (201) once
/// implemented, and <c>GET /tenants</c> should return only the caller's own tenants. Noted
/// briefly per task instructions; moving on.
/// </remarks>
public sealed class UnscopedOperationTests : IClassFixture<ApiFactory>
{
    private readonly ApiFactory _factory;

    public UnscopedOperationTests(SqlServerFixture sqlServerFixture, ApiFactory factory)
    {
        _factory = factory;
        _factory.UseConnectionString(sqlServerFixture.ConnectionString);
    }

    [Fact]
    public async Task Post_Tenants_WithoutAnyTenantContext_Succeeds()
    {
        await _factory.InitializeDatabaseAsync();
        await _factory.SeedTwoTenantsAsync();

        // A brand-new, never-seeded Entra identity — there is no membership-based gate on
        // this route, so tenant creation must work even though the caller has no tenant
        // context established yet.
        using var client = _factory.CreateClient();
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("TestScheme", "test");
        client.DefaultRequestHeaders.Add("X-Test-Oid", Guid.NewGuid().ToString());
        client.DefaultRequestHeaders.Add("X-Test-Tid", Guid.NewGuid().ToString());
        client.DefaultRequestHeaders.Add("Idempotency-Key", Guid.NewGuid().ToString());

        var response = await client.PostAsync(
            "/tenants",
            JsonContent("Brand New Tenant"),
            TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.Created);
    }

    [Fact]
    public async Task Get_Tenants_ForTenantAMember_ReturnsOnlyTenantA_NotTenantB()
    {
        await _factory.InitializeDatabaseAsync();
        var seed = await _factory.SeedTwoTenantsAsync();

        using var client = CreateAuthenticatedClient(seed.TenantA.EntraObjectId, seed.TenantA.EntraTenantId);

        var response = await client.GetAsync("/tenants", TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.OK);

        var body = await response.Content.ReadAsStringAsync(TestContext.Current.CancellationToken);

        body.Should().Contain(seed.TenantA.TenantId.Value.ToString());
        body.Should().NotContain(seed.TenantB.TenantId.Value.ToString());
        body.Should().NotContain("Tenant B");
    }

    [Fact]
    public async Task Get_Tenants_ForUserWithNoMemberships_ReturnsEmptyArray()
    {
        await _factory.InitializeDatabaseAsync();
        await _factory.SeedTwoTenantsAsync();

        // A fresh, never-seeded Entra identity with no memberships anywhere.
        using var client = CreateAuthenticatedClient(Guid.NewGuid(), Guid.NewGuid());

        var response = await client.GetAsync("/tenants", TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.OK);

        var payload = await response.Content.ReadFromJsonAsync<object[]>(
            TestContext.Current.CancellationToken);

        payload.Should().NotBeNull();
        payload.Should().BeEmpty();
    }

    private HttpClient CreateAuthenticatedClient(Guid entraObjectId, Guid entraTenantId)
    {
        var client = _factory.CreateClient();
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("TestScheme", "test");
        client.DefaultRequestHeaders.Add("X-Test-Oid", entraObjectId.ToString());
        client.DefaultRequestHeaders.Add("X-Test-Tid", entraTenantId.ToString());
        return client;
    }

    private static JsonContent JsonContent(object displayName) =>
        System.Net.Http.Json.JsonContent.Create(new { displayName });
}
