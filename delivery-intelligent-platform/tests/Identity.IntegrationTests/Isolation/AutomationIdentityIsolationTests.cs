using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using AwesomeAssertions;
using Identity.IntegrationTests.Infrastructure;
using Xunit;

namespace Identity.IntegrationTests.Isolation;

/// <summary>
/// ADR-022: an application identity holding <c>Tenancy.Automation.Member</c> is a tenant member
/// like any user — tenant isolation applies to it unchanged — and a token with neither the user
/// scope nor that role is refused.
/// </summary>
public sealed class AutomationIdentityIsolationTests : IdentityIntegrationTestBase
{
    private const string AutomationRole = "Tenancy.Automation.Member";

    public AutomationIdentityIsolationTests(SqlServerFixture sqlServerFixture, ApiFactory factory)
        : base(sqlServerFixture, factory)
    {
    }

    [Fact]
    public async Task AutomationIdentity_IsRefusedOnATenantItIsNotAMemberOf_ExactlyLikeAUser()
    {
        await Factory.InitializeDatabaseAsync();
        var seed = await Factory.SeedTwoTenantsAsync();
        var tenantB = $"/tenants/{seed.TenantB.TenantId.Value}";

        using var automation = CreateClient(Guid.NewGuid(), Guid.NewGuid(), roles: AutomationRole);
        using var user = CreateClient(seed.TenantA.EntraObjectId, seed.TenantA.EntraTenantId);

        var automationResponse = await automation.GetAsync(tenantB, TestContext.Current.CancellationToken);
        var userResponse = await user.GetAsync(tenantB, TestContext.Current.CancellationToken);
        var neverSeeded = await automation.GetAsync($"/tenants/{Guid.NewGuid()}", TestContext.Current.CancellationToken);

        automationResponse.StatusCode.Should().Be(HttpStatusCode.NotFound);
        automationResponse.StatusCode.Should().Be(userResponse.StatusCode);
        automationResponse.StatusCode.Should().Be(neverSeeded.StatusCode);

        var automationBody = await automationResponse.Content.ReadAsStringAsync(TestContext.Current.CancellationToken);
        var userBody = await userResponse.Content.ReadAsStringAsync(TestContext.Current.CancellationToken);
        automationBody.Should().Be(userBody);
    }

    [Fact]
    public async Task AutomationIdentity_CanReadATenantItCreated()
    {
        await Factory.InitializeDatabaseAsync();

        using var automation = CreateClient(Guid.NewGuid(), Guid.NewGuid(), roles: AutomationRole);
        automation.DefaultRequestHeaders.Add("Idempotency-Key", Guid.NewGuid().ToString());

        var created = await automation.PostAsJsonAsync(
            "/tenants", new { displayName = "loadtest-01" }, TestContext.Current.CancellationToken);
        created.StatusCode.Should().Be(HttpStatusCode.Created);

        var tenant = await created.Content.ReadFromJsonAsync<CreatedTenant>(TestContext.Current.CancellationToken);
        var read = await automation.GetAsync($"/tenants/{tenant!.Id}", TestContext.Current.CancellationToken);

        read.StatusCode.Should().Be(HttpStatusCode.OK);
    }

    [Fact]
    public async Task Token_WithAnUnrelatedRole_IsRefused()
    {
        await Factory.InitializeDatabaseAsync();

        using var client = CreateClient(Guid.NewGuid(), Guid.NewGuid(), roles: "Some.Other.Role");

        var response = await client.GetAsync("/tenants", TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.Forbidden);
    }

    [Fact]
    public async Task Token_WithAnUnrelatedScope_IsRefused()
    {
        await Factory.InitializeDatabaseAsync();

        using var client = CreateClient(Guid.NewGuid(), Guid.NewGuid(), scope: "user_impersonation");

        var response = await client.GetAsync("/tenants", TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.Forbidden);
    }

    private HttpClient CreateClient(Guid oid, Guid tid, string? roles = null, string? scope = null)
    {
        var client = Factory.CreateClient();
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("TestScheme", "test");
        client.DefaultRequestHeaders.Add("X-Test-Oid", oid.ToString());
        client.DefaultRequestHeaders.Add("X-Test-Tid", tid.ToString());
        if (roles is not null)
        {
            client.DefaultRequestHeaders.Add("X-Test-Roles", roles);
        }

        if (scope is not null)
        {
            client.DefaultRequestHeaders.Add("X-Test-Scp", scope);
        }

        return client;
    }

    private sealed record CreatedTenant(Guid Id);
}
