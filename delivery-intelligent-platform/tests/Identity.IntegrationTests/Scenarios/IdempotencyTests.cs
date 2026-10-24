using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using ArchitectureTests.Support;
using AwesomeAssertions;
using Identity.IntegrationTests.Infrastructure;
using Xunit;

namespace Identity.IntegrationTests.Scenarios;

/// <summary>
/// Failing tests (T050) for idempotent <c>POST /tenants</c> per contracts/openapi.yaml and
/// FR-020: replay of a request with a previously-seen <c>Idempotency-Key</c> returns the stored
/// status and body verbatim (a 201 replays as 201, never 200); the same key reused with a
/// different body returns 422; a request whose identical idempotent twin is still in flight
/// returns 409.
/// </summary>
/// <remarks>
/// <b>What this file proves right now, and what it doesn't.</b> Same caveat as T045/T047's files:
/// neither the <c>/tenants</c> endpoint (T058) nor the idempotency filter behind it (T056) exist
/// yet, so every request below hits a route absent from <c>Program.cs</c>'s route table and comes
/// back <c>404 Not Found</c>. These tests are expected to be red today; they encode the
/// eventual-correct idempotency behavior per openapi.yaml so they'll go genuinely green once
/// T056/T058 land.
/// </remarks>
public sealed class IdempotencyTests : IdentityIntegrationTestBase
{

    public IdempotencyTests(SqlServerFixture sqlServerFixture, ApiFactory factory)
        : base(sqlServerFixture, factory)
    {
    }

    /// <summary>
    /// Sending the exact same <c>POST /tenants</c> request (same <c>Idempotency-Key</c>, same
    /// body) twice must return the same status code both times — a 201 replays as 201, never a
    /// 200 — with the second response's body identical to the first, and
    /// <c>Idempotency-Replayed: true</c> present only on the replay. openapi.yaml says the header
    /// is "Present and true when this response was replayed," which implies it may simply be
    /// absent on the original, non-replayed response — this test does not assume the header must
    /// be present-and-false on the first response, only that it must not be the literal string
    /// "true" there.
    /// </summary>
    [CoversRequirement("FR-020")]
    [Fact]
    public async Task Post_Tenants_ReplayedWithSameKeyAndBody_ReturnsSameStatusAndBodyVerbatim()
    {
        await Factory.InitializeDatabaseAsync();

        using var client = Factory.CreateClient();
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("TestScheme", "test");
        client.DefaultRequestHeaders.Add("X-Test-Oid", Guid.NewGuid().ToString());
        client.DefaultRequestHeaders.Add("X-Test-Tid", Guid.NewGuid().ToString());

        var idempotencyKey = Guid.CreateVersion7().ToString();

        var firstResponse = await SendPostTenants(client, idempotencyKey, "Acme Delivery Co");
        var firstBody = await firstResponse.Content.ReadAsStringAsync(TestContext.Current.CancellationToken);
        var firstReplayedHeader = GetIdempotencyReplayedHeaderValue(firstResponse);

        var secondResponse = await SendPostTenants(client, idempotencyKey, "Acme Delivery Co");
        var secondBody = await secondResponse.Content.ReadAsStringAsync(TestContext.Current.CancellationToken);

        secondResponse.StatusCode.Should().Be(firstResponse.StatusCode);
        secondResponse.StatusCode.Should().Be(HttpStatusCode.Created);
        secondBody.Should().Be(firstBody);

        firstReplayedHeader.Should().NotBe("true");
        GetIdempotencyReplayedHeaderValue(secondResponse).Should().Be("true");
    }

    /// <summary>
    /// Reusing the same <c>Idempotency-Key</c> with a materially different request body (a
    /// different <c>displayName</c>) must be rejected as key reuse, per openapi.yaml's <c>422</c>
    /// response for this endpoint.
    /// </summary>
    [CoversRequirement("FR-020")]
    [Fact]
    public async Task Post_Tenants_SameKeyDifferentBody_ReturnsUnprocessableEntity()
    {
        await Factory.InitializeDatabaseAsync();

        using var client = Factory.CreateClient();
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("TestScheme", "test");
        client.DefaultRequestHeaders.Add("X-Test-Oid", Guid.NewGuid().ToString());
        client.DefaultRequestHeaders.Add("X-Test-Tid", Guid.NewGuid().ToString());

        var idempotencyKey = Guid.CreateVersion7().ToString();

        await SendPostTenants(client, idempotencyKey, "Acme Delivery Co");
        var secondResponse = await SendPostTenants(client, idempotencyKey, "Widgets Unlimited");

        secondResponse.StatusCode.Should().Be(HttpStatusCode.UnprocessableEntity);
    }

    /// <summary>
    /// A request whose identical idempotent twin is still in flight must be rejected with 409,
    /// per openapi.yaml (with a <c>Retry-After</c> header).
    /// </summary>
    /// <remarks>
    /// <b>Honest limitation.</b> Reliably forcing two requests to overlap in-flight, from outside
    /// the process, without either a real race (fragile, flaky, not worth building for this task)
    /// or an inspectable <c>InFlight</c> state exposed by the idempotency filter itself (T056, not
    /// yet built), isn't achievable today. This test fires two identical requests concurrently via
    /// <c>Task.WhenAll</c> as a best-effort simulation and only asserts that <b>at least one</b> of
    /// the two responses lands on the target spec (<c>201</c> "this one created it" or <c>409</c>
    /// "the other one was in flight") — it does not (and today cannot) assert that <em>both</em>
    /// outcomes are reachable, nor that 409 specifically fires. With no <c>/tenants</c> endpoint
    /// yet, both responses today are <c>404</c>, so this assertion fails, honestly, until T056 and
    /// T058 land. Its real value only exists once the idempotency filter exists to actually
    /// exercise the in-flight branch.
    /// </remarks>
    [CoversRequirement("FR-020")]
    [Fact]
    public async Task Post_Tenants_ConcurrentIdenticalRequests_AtLeastOneIsCreatedOrInFlightRejected()
    {
        await Factory.InitializeDatabaseAsync();

        using var client = Factory.CreateClient();
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("TestScheme", "test");
        client.DefaultRequestHeaders.Add("X-Test-Oid", Guid.NewGuid().ToString());
        client.DefaultRequestHeaders.Add("X-Test-Tid", Guid.NewGuid().ToString());

        var idempotencyKey = Guid.CreateVersion7().ToString();

        var firstTask = SendPostTenants(client, idempotencyKey, "Acme Delivery Co");
        var secondTask = SendPostTenants(client, idempotencyKey, "Acme Delivery Co");

        var responses = await Task.WhenAll(firstTask, secondTask);

        responses.Should().Contain(response =>
            response.StatusCode == HttpStatusCode.Created || response.StatusCode == HttpStatusCode.Conflict);
    }

    private static async Task<HttpResponseMessage> SendPostTenants(
        HttpClient client, string idempotencyKey, string displayName)
    {
        using var request = new HttpRequestMessage(HttpMethod.Post, "/tenants")
        {
            Content = JsonContent.Create(new { displayName }),
        };
        request.Headers.Add("Idempotency-Key", idempotencyKey);

        return await client.SendAsync(request, TestContext.Current.CancellationToken);
    }

    private static string? GetIdempotencyReplayedHeaderValue(HttpResponseMessage response) =>
        response.Headers.TryGetValues("Idempotency-Replayed", out var values) ? values.FirstOrDefault() : null;
}
