using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using AwesomeAssertions;
using Tenancy.IntegrationTests.Infrastructure;
using Xunit;

namespace Tenancy.IntegrationTests.Scenarios;

/// <summary>
/// Failing tests (T051) for <c>PATCH /tenants/{tenantId}</c> concurrency control per
/// contracts/openapi.yaml and FR-021: a missing <c>If-Match</c> header is <b>428</b>
/// (Precondition Required); a stale <c>If-Match</c> (doesn't match the resource's current
/// <c>rowversion</c>) is <b>412</b> (Precondition Failed); a genuine race at save time — two
/// concurrent requests both pass their own request-time <c>If-Match</c> check but only one save
/// wins — is <b>409</b> (Conflict).
/// </summary>
/// <remarks>
/// <b>What this file proves right now, and what it doesn't.</b> Same caveat as T045/T047/T050's
/// files: neither the <c>/tenants/{tenantId}</c> PATCH endpoint (T058) nor the ETag/<c>If-Match</c>
/// helper behind it (T057) exist yet, so every request below hits a route absent from
/// <c>Program.cs</c>'s route table and comes back <c>404 Not Found</c> instead of the target
/// <c>428</c>/<c>412</c>/<c>409</c>. These tests are expected to be red today; they encode the
/// eventual-correct concurrency behavior per openapi.yaml so they'll go genuinely green once
/// T057/T058 land.
/// </remarks>
public sealed class ConcurrencyTests : IClassFixture<ApiFactory>
{
    private readonly ApiFactory _factory;

    public ConcurrencyTests(SqlServerFixture sqlServerFixture, ApiFactory factory)
    {
        _factory = factory;
        _factory.UseConnectionString(sqlServerFixture.ConnectionString);
    }

    /// <summary>
    /// Test 1: a <c>PATCH /tenants/{tenantId}</c> request with a valid body but no
    /// <c>If-Match</c> header at all must be rejected with <c>428 Precondition Required</c> —
    /// the caller never told the server which version it believes it's updating.
    /// </summary>
    [Fact]
    public async Task Patch_Tenant_WithoutIfMatchHeader_ReturnsPreconditionRequired()
    {
        await _factory.InitializeDatabaseAsync();
        var seed = await _factory.SeedTwoTenantsAsync();

        using var client = CreateAuthenticatedClient(seed.TenantA);

        var response = await client.PatchAsync(
            $"/tenants/{seed.TenantA.TenantId.Value}",
            DisplayNameContent("Renamed Tenant A"),
            TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be((HttpStatusCode)428);
    }

    /// <summary>
    /// Test 2: a caller reads the tenant's current ETag, someone else's PATCH changes the
    /// <c>rowversion</c> in between, and the caller then PATCHes using its now-stale
    /// (originally-read) <c>If-Match</c> value. That must be rejected with
    /// <c>412 Precondition Failed</c> — the caller's view of the resource was out of date at
    /// request time, distinct from a save-time race (Test 3).
    /// </summary>
    /// <remarks>
    /// This flow depends on endpoints (GET's ETag response header, PATCH's success path) that
    /// don't exist yet, so it's written as the target-spec flow anyway, per this task's brief.
    /// </remarks>
    [Fact]
    public async Task Patch_Tenant_WithStaleIfMatch_ReturnsPreconditionFailed()
    {
        await _factory.InitializeDatabaseAsync();
        var seed = await _factory.SeedTwoTenantsAsync();

        using var client = CreateAuthenticatedClient(seed.TenantA);
        var tenantUri = $"/tenants/{seed.TenantA.TenantId.Value}";

        var initialGet = await client.GetAsync(tenantUri, TestContext.Current.CancellationToken);
        var originalEtag = initialGet.Headers.ETag;

        using var firstPatch = new HttpRequestMessage(HttpMethod.Patch, tenantUri)
        {
            Content = DisplayNameContent("First Update"),
        };
        if (originalEtag is not null)
        {
            firstPatch.Headers.IfMatch.Add(originalEtag);
        }

        var firstPatchResponse = await client.SendAsync(firstPatch, TestContext.Current.CancellationToken);
        firstPatchResponse.StatusCode.Should().Be(HttpStatusCode.OK);

        using var secondPatch = new HttpRequestMessage(HttpMethod.Patch, tenantUri)
        {
            Content = DisplayNameContent("Second Update Using Stale ETag"),
        };
        if (originalEtag is not null)
        {
            secondPatch.Headers.IfMatch.Add(originalEtag);
        }

        var secondPatchResponse = await client.SendAsync(secondPatch, TestContext.Current.CancellationToken);

        secondPatchResponse.StatusCode.Should().Be((HttpStatusCode)412);
    }

    /// <summary>
    /// Test 3: two concurrent <c>PATCH</c> requests, both carrying the <b>same</b>,
    /// valid-at-dispatch-time <c>If-Match</c> value, race to save. Both pass their own
    /// request-time precondition check, but only one save can win — EF Core's own optimistic
    /// concurrency exception on the loser is translated to <c>409 Conflict</c>, distinct from
    /// the request-time staleness of Test 2.
    /// </summary>
    /// <remarks>
    /// <b>Honest limitation.</b> Same honesty standard as T050's Test 3. Reliably forcing two
    /// requests to interleave at the exact save instant — so that both pass the precondition
    /// check and only the database's optimistic-concurrency token decides the loser — isn't
    /// achievable from outside the process without either a real, fragile race or an
    /// inspectable hook into the save pipeline that doesn't exist yet. This test fires two
    /// identical-If-Match PATCHes concurrently via <c>Task.WhenAll</c> as a best-effort
    /// simulation and only asserts that <b>at least one</b> of the two responses lands on the
    /// target spec (<c>200</c> "this one won the save race" or <c>409</c> "this one lost it") —
    /// it does not (and today cannot) assert that <em>both</em> outcomes are reachable, nor that
    /// 409 specifically fires for a genuine save-time race rather than some other cause. With no
    /// <c>/tenants/{tenantId}</c> PATCH endpoint yet, both responses today are <c>404</c>, so
    /// this assertion fails, honestly, until T057 and T058 land. A fully deterministic test that
    /// forces true interleaving at the save instant (e.g. via a save-pipeline test hook or
    /// SaveChanges interception) is future work, not this task's job to solve.
    /// </remarks>
    [Fact]
    public async Task Patch_Tenant_ConcurrentRequestsWithSameIfMatch_AtLeastOneSucceedsOrConflicts()
    {
        await _factory.InitializeDatabaseAsync();
        var seed = await _factory.SeedTwoTenantsAsync();

        using var client = CreateAuthenticatedClient(seed.TenantA);
        var tenantUri = $"/tenants/{seed.TenantA.TenantId.Value}";

        var initialGet = await client.GetAsync(tenantUri, TestContext.Current.CancellationToken);
        var sharedEtag = initialGet.Headers.ETag;

        Task<HttpResponseMessage> SendPatch(string displayName)
        {
            var request = new HttpRequestMessage(HttpMethod.Patch, tenantUri)
            {
                Content = DisplayNameContent(displayName),
            };
            if (sharedEtag is not null)
            {
                request.Headers.IfMatch.Add(sharedEtag);
            }

            return client.SendAsync(request, TestContext.Current.CancellationToken);
        }

        var firstTask = SendPatch("Concurrent Update A");
        var secondTask = SendPatch("Concurrent Update B");

        var responses = await Task.WhenAll(firstTask, secondTask);

        responses.Should().Contain(response =>
            response.StatusCode == HttpStatusCode.OK || response.StatusCode == HttpStatusCode.Conflict);
    }

    private HttpClient CreateAuthenticatedClient(SeededTenant seededTenant)
    {
        var client = _factory.CreateClient();
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("TestScheme", "test");
        client.DefaultRequestHeaders.Add("X-Test-Oid", seededTenant.EntraObjectId.ToString());
        client.DefaultRequestHeaders.Add("X-Test-Tid", seededTenant.EntraTenantId.ToString());
        return client;
    }

    private static JsonContent DisplayNameContent(string displayName) =>
        JsonContent.Create(new { displayName });
}
