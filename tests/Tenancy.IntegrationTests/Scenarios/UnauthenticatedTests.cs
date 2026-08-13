using System.Net;
using System.Net.Http.Json;
using Tenancy.IntegrationTests.Infrastructure;
using AwesomeAssertions;
using Xunit;

namespace Tenancy.IntegrationTests.Scenarios;

/// <summary>
/// Failing test (T046) asserting <b>401 Unauthorized</b> for every tenant operation when no
/// <c>Authorization</c> header is present at all (the T040 <c>TestAuthHandler</c>
/// <c>NoResult()</c> path — not "present but invalid", which is a different case).
/// </summary>
/// <remarks>
/// <b>What this file proves right now, and what it doesn't.</b> As confirmed while reviewing
/// T045: <c>Program.cs</c>'s pipeline runs <c>UseAuthentication()</c> → <c>UseAuthorization()</c>,
/// but for a route that doesn't match any endpoint (the <c>/tenants</c> endpoints don't exist
/// yet; T058 adds them), the request never reaches an endpoint, so <c>UseAuthorization</c> is a
/// no-op and the request falls through to a plain 404 — not a 401. These tests are written as the
/// real, eventual-correct spec (assert <c>Unauthorized</c> specifically) and are expected to fail
/// today with a genuine 401-vs-404 assertion mismatch, not weakened to "not 200" just to pass
/// prematurely. They'll go genuinely green once T058 lands the endpoints behind authentication.
/// </remarks>
public sealed class UnauthenticatedTests : IClassFixture<ApiFactory>
{
    private readonly ApiFactory _factory;

    public UnauthenticatedTests(SqlServerFixture sqlServerFixture, ApiFactory factory)
    {
        _factory = factory;
        _factory.UseConnectionString(sqlServerFixture.ConnectionString);
    }

    [Fact]
    public async Task Post_Tenants_WithNoAuthorizationHeader_ReturnsUnauthorized()
    {
        await _factory.InitializeDatabaseAsync();

        using var client = _factory.CreateClient();

        var response = await client.PostAsync(
            "/tenants",
            JsonContent("Acme Delivery Co"),
            TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.Unauthorized);
    }

    [Fact]
    public async Task Get_Tenants_WithNoAuthorizationHeader_ReturnsUnauthorized()
    {
        await _factory.InitializeDatabaseAsync();

        using var client = _factory.CreateClient();

        var response = await client.GetAsync("/tenants", TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.Unauthorized);
    }

    [Fact]
    public async Task Get_TenantById_WithNoAuthorizationHeader_ReturnsUnauthorized()
    {
        await _factory.InitializeDatabaseAsync();

        using var client = _factory.CreateClient();

        var response = await client.GetAsync(
            $"/tenants/{Guid.NewGuid()}",
            TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.Unauthorized);
    }

    [Fact]
    public async Task Patch_TenantById_WithNoAuthorizationHeader_ReturnsUnauthorized()
    {
        await _factory.InitializeDatabaseAsync();

        using var client = _factory.CreateClient();

        var response = await client.PatchAsync(
            $"/tenants/{Guid.NewGuid()}",
            JsonContent("Renamed Tenant"),
            TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.Unauthorized);
    }

    private static JsonContent JsonContent(object payload) =>
        System.Net.Http.Json.JsonContent.Create(new { displayName = payload });
}
