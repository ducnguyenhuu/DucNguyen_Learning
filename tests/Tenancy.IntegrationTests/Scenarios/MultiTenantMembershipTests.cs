using System.Net;
using System.Net.Http.Headers;
using AwesomeAssertions;
using Tenancy.IntegrationTests.Infrastructure;
using Xunit;

namespace Tenancy.IntegrationTests.Scenarios;

/// <summary>
/// Failing multi-tenant membership test (T049): one user holding an active membership in
/// <b>two</b> tenants authenticates once and operates against each tenant in turn, and no
/// response blends data across them (FR-010).
/// </summary>
/// <remarks>
/// Distinct from T048 (a user in only one tenant not seeing another's data): this test's angle
/// is the opposite failure mode — a user who legitimately belongs to <em>both</em> tenants must
/// see both, correctly separated, and never merged into one blended record. Like the other
/// Scenarios files, the <c>/tenants</c> endpoints don't exist yet (T058 adds them), so this is
/// expected to fail/behave per the same "route absent" situation as prior files until then.
/// </remarks>
public sealed class MultiTenantMembershipTests : IClassFixture<ApiFactory>
{
    private readonly ApiFactory _factory;

    public MultiTenantMembershipTests(SqlServerFixture sqlServerFixture, ApiFactory factory)
    {
        _factory = factory;
        _factory.UseConnectionString(sqlServerFixture.ConnectionString);
    }

    [Fact]
    public async Task Get_TenantById_ForEachTenant_ReturnsThatTenantsOwnData_NeverBlended()
    {
        await _factory.InitializeDatabaseAsync();
        var seed = await _factory.SeedOneUserInTwoTenantsAsync();

        using var client = CreateAuthenticatedClient(seed.User);

        var responseX = await client.GetAsync(
            $"/tenants/{seed.TenantX.TenantId.Value}",
            TestContext.Current.CancellationToken);

        responseX.StatusCode.Should().Be(HttpStatusCode.OK);

        var bodyX = await responseX.Content.ReadAsStringAsync(TestContext.Current.CancellationToken);
        bodyX.Should().Contain(seed.TenantX.DisplayName);
        bodyX.Should().NotContain(seed.TenantY.DisplayName);

        var responseY = await client.GetAsync(
            $"/tenants/{seed.TenantY.TenantId.Value}",
            TestContext.Current.CancellationToken);

        responseY.StatusCode.Should().Be(HttpStatusCode.OK);

        var bodyY = await responseY.Content.ReadAsStringAsync(TestContext.Current.CancellationToken);
        bodyY.Should().Contain(seed.TenantY.DisplayName);
        bodyY.Should().NotContain(seed.TenantX.DisplayName);
    }

    [Fact]
    public async Task Get_Tenants_ForUserInBothTenants_ReturnsBothTenants_CorrectlySeparated()
    {
        await _factory.InitializeDatabaseAsync();
        var seed = await _factory.SeedOneUserInTwoTenantsAsync();

        using var client = CreateAuthenticatedClient(seed.User);

        var response = await client.GetAsync("/tenants", TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.OK);

        var body = await response.Content.ReadAsStringAsync(TestContext.Current.CancellationToken);
        body.Should().Contain(seed.TenantX.TenantId.Value.ToString());
        body.Should().Contain(seed.TenantY.TenantId.Value.ToString());
        body.Should().Contain(seed.TenantX.DisplayName);
        body.Should().Contain(seed.TenantY.DisplayName);
    }

    private HttpClient CreateAuthenticatedClient(SharedUserSeed sharedUser)
    {
        var client = _factory.CreateClient();
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("TestScheme", "test");
        client.DefaultRequestHeaders.Add("X-Test-Oid", sharedUser.EntraObjectId.ToString());
        client.DefaultRequestHeaders.Add("X-Test-Tid", sharedUser.EntraTenantId.ToString());
        return client;
    }
}
