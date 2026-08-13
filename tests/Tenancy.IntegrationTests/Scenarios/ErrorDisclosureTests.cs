using System.Net.Http.Headers;
using AwesomeAssertions;
using Tenancy.IntegrationTests.Infrastructure;
using Xunit;

namespace Tenancy.IntegrationTests.Scenarios;

/// <summary>
/// Failing error non-disclosure tests (T052) — black-box verification of T038's global
/// <c>ProblemDetailsHandler</c> (RFC 9457, zero exception detail) across a variety of
/// error-triggering scenarios (FR-022).
/// </summary>
/// <remarks>
/// This file does not add production code; T038 already implemented the handler this exercises.
/// Each test below provokes a different class of would-be-error (malformed route parameter,
/// malformed request body, cross-tenant read) and asserts the response body — whatever its
/// status code turns out to be — never contains a stack trace, exception type name, connection
/// string fragment, raw SQL statement, or another tenant's identifying information. As with the
/// other Isolation-adjacent scaffolding (T043/T044), several of the endpoints under test
/// (<c>/tenants/{tenantId}</c>, <c>POST /tenants</c>) do not exist yet in <c>Program.cs</c>'s
/// route table — this test intentionally records whatever ASP.NET Core actually returns today
/// (a routing-table 404, or a framework-level 400 for malformed JSON) rather than forcing an
/// assumption about which layer produces the response.
/// </remarks>
public sealed class ErrorDisclosureTests : IClassFixture<ApiFactory>
{
    private readonly ApiFactory _factory;

    public ErrorDisclosureTests(SqlServerFixture sqlServerFixture, ApiFactory factory)
    {
        _factory = factory;
        _factory.UseConnectionString(sqlServerFixture.ConnectionString);
    }

    [Fact]
    public async Task Get_TenantById_WithMalformedRouteId_DoesNotDiscloseSensitiveDetail()
    {
        await _factory.InitializeDatabaseAsync();

        using var client = CreateAuthenticatedClient(Guid.NewGuid(), Guid.NewGuid());

        // "not-a-guid" is a genuinely malformed tenant id — not a syntactically valid GUID at
        // all — so this exercises route-model-binding failure, whatever status it produces.
        var response = await client.GetAsync(
            "/tenants/not-a-guid",
            TestContext.Current.CancellationToken);

        var body = await response.Content.ReadAsStringAsync(TestContext.Current.CancellationToken);

        AssertNoSensitiveDisclosure(body);
    }

    [Fact]
    public async Task Post_Tenants_WithMalformedJsonBody_DoesNotDiscloseSensitiveDetail()
    {
        await _factory.InitializeDatabaseAsync();

        using var client = CreateAuthenticatedClient(Guid.NewGuid(), Guid.NewGuid());

        using var malformedContent = new StringContent(
            "{ this is not valid json ",
            System.Text.Encoding.UTF8,
            "application/json");

        var response = await client.PostAsync(
            "/tenants",
            malformedContent,
            TestContext.Current.CancellationToken);

        var body = await response.Content.ReadAsStringAsync(TestContext.Current.CancellationToken);

        AssertNoSensitiveDisclosure(body);
    }

    [Fact]
    public async Task Get_TenantById_ForOtherTenant_DoesNotDiscloseOtherTenantIdentity()
    {
        await _factory.InitializeDatabaseAsync();
        var seed = await _factory.SeedTwoTenantsAsync();

        using var client = CreateAuthenticatedClient(
            seed.TenantA.EntraTenantId,
            seed.TenantA.EntraObjectId);

        // T044's scenario, viewed from a different angle: not "is this indistinguishable from a
        // never-seeded tenant" (T044's concern) but "does the body itself leak anything sensitive
        // at all" — including Tenant B's own identifiers/display name.
        var response = await client.GetAsync(
            $"/tenants/{seed.TenantB.TenantId.Value}",
            TestContext.Current.CancellationToken);

        var body = await response.Content.ReadAsStringAsync(TestContext.Current.CancellationToken);

        AssertNoSensitiveDisclosure(body);
        body.Should().NotContain(seed.TenantB.TenantId.Value.ToString());
        body.Should().NotContain("Tenant B");
    }

    private HttpClient CreateAuthenticatedClient(Guid entraTenantId, Guid entraObjectId)
    {
        var client = _factory.CreateClient();
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("TestScheme", "test");
        client.DefaultRequestHeaders.Add("X-Test-Oid", entraObjectId.ToString());
        client.DefaultRequestHeaders.Add("X-Test-Tid", entraTenantId.ToString());
        return client;
    }

    /// <summary>
    /// Shared assertion helper (per task brief): a response body must never contain a stack
    /// trace, exception type name, connection-string fragment, or raw SQL statement fragment.
    /// Tenant-identifier disclosure is checked per-test (the sensitive value differs by
    /// scenario), not here.
    /// </summary>
    private static void AssertNoSensitiveDisclosure(string body)
    {
        body.Should().NotContain("Exception");
        body.Should().NotContain("StackTrace");
        body.Should().NotContain("   at ");
        body.Should().NotContain("System.");

        body.Should().NotContain("Server=");
        body.Should().NotContain("Password=");
        body.Should().NotContain("User Id=");

        body.Should().NotContainEquivalentOf("SELECT ");
        body.Should().NotContainEquivalentOf("INSERT ");
        body.Should().NotContainEquivalentOf("UPDATE ");
        body.Should().NotContainEquivalentOf("FROM [");
        body.Should().NotContainEquivalentOf("WHERE [");
    }
}
