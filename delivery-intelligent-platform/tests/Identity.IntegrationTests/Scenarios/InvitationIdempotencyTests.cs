using System.Net;
using System.Net.Http.Json;
using ArchitectureTests.Support;
using AwesomeAssertions;
using Identity.Domain.Abstractions;
using Identity.IntegrationTests.Infrastructure;
using Xunit;

namespace Identity.IntegrationTests.Scenarios;

/// <summary>
/// FR-020's idempotency guarantee on <c>POST /invitations</c>, the one idempotent endpoint
/// (<c>IdempotencyFilter</c>, wired by <c>WithIdempotency()</c>): a replay with a previously seen
/// <c>Idempotency-Key</c> returns the stored status and body verbatim (a 201 replays as 201,
/// never 200) without creating a second invitation; the same key reused with a different body
/// returns 422; and a request whose identical twin is still in flight returns 409.
/// </summary>
/// <remarks>
/// The idempotency record is keyed by <c>(CreatedByUserId, Endpoint, Key)</c> (ADR-025,
/// decision 7), so a key is private to the caller who used it: a second administrator reusing the
/// same key value is a different request, not a replay.
/// </remarks>
public sealed class InvitationIdempotencyTests : IdentityIntegrationTestBase
{
    public InvitationIdempotencyTests(SqlServerFixture sqlServerFixture, ApiFactory factory)
        : base(sqlServerFixture, factory)
    {
    }

    /// <summary>
    /// Sending the exact same request twice returns the same status both times, the second body
    /// identical to the first, <c>Idempotency-Replayed: true</c> only on the replay, and exactly
    /// one invitation persisted (confirmed via <c>GET /invitations</c>). openapi.yaml says the
    /// header is "Present and true when this response was replayed", so it may simply be absent on
    /// the original — the test only requires it not to be "true" there.
    /// </summary>
    [CoversRequirement("FR-020")]
    [Fact]
    public async Task Post_Invitations_ReplayedWithSameKeyAndBody_ReturnsSameStatusAndBodyVerbatim_AndOnlyOneInvitationExists()
    {
        var administrator = await Factory.SeedMemberAsync(Role.Administrator);
        using var client = Factory.CreateClientFor(administrator);

        var idempotencyKey = Guid.CreateVersion7().ToString();
        const string invitedEmail = "invitee@example.com";

        var firstResponse = await SendPostInvitation(client, idempotencyKey, invitedEmail, "Member");
        var firstBody = await firstResponse.Content.ReadAsStringAsync(TestContext.Current.CancellationToken);
        var firstReplayedHeader = GetIdempotencyReplayedHeaderValue(firstResponse);

        var secondResponse = await SendPostInvitation(client, idempotencyKey, invitedEmail, "Member");
        var secondBody = await secondResponse.Content.ReadAsStringAsync(TestContext.Current.CancellationToken);

        secondResponse.StatusCode.Should().Be(firstResponse.StatusCode);
        secondResponse.StatusCode.Should().Be(HttpStatusCode.Created);
        secondBody.Should().Be(firstBody);

        firstReplayedHeader.Should().NotBe("true");
        GetIdempotencyReplayedHeaderValue(secondResponse).Should().Be("true");

        var listResponse = await client.GetAsync("/invitations", TestContext.Current.CancellationToken);
        listResponse.StatusCode.Should().Be(HttpStatusCode.OK);

        var listBody = await listResponse.Content.ReadAsStringAsync(TestContext.Current.CancellationToken);
        CountOccurrences(listBody, invitedEmail).Should().Be(1);
    }

    /// <summary>
    /// Reusing the same key with a materially different body (a different invited email) is
    /// rejected as key reuse with 422.
    /// </summary>
    [CoversRequirement("FR-020")]
    [Fact]
    public async Task Post_Invitations_SameKeyDifferentBody_ReturnsUnprocessableEntity()
    {
        var administrator = await Factory.SeedMemberAsync(Role.Administrator);
        using var client = Factory.CreateClientFor(administrator);

        var idempotencyKey = Guid.CreateVersion7().ToString();

        await SendPostInvitation(client, idempotencyKey, "first-invitee@example.com", "Member");
        var secondResponse = await SendPostInvitation(client, idempotencyKey, "second-invitee@example.com", "Member");

        secondResponse.StatusCode.Should().Be(HttpStatusCode.UnprocessableEntity);
    }

    /// <summary>
    /// Two identical requests fired concurrently: whichever loses either sees its twin in flight
    /// (409) or replays the finished result (201). Either way at least one response is the
    /// original 201, and only one invitation exists.
    /// </summary>
    /// <remarks>
    /// <b>Honest limitation.</b> Forcing the two requests to overlap in flight from outside the
    /// process is not deterministic, so this asserts the outcome set rather than that 409
    /// specifically fires.
    /// </remarks>
    [CoversRequirement("FR-020")]
    [Fact]
    public async Task Post_Invitations_ConcurrentIdenticalRequests_CreateExactlyOneInvitation()
    {
        var administrator = await Factory.SeedMemberAsync(Role.Administrator);
        using var client = Factory.CreateClientFor(administrator);

        var idempotencyKey = Guid.CreateVersion7().ToString();
        const string invitedEmail = "concurrent-invitee@example.com";

        var responses = await Task.WhenAll(
            SendPostInvitation(client, idempotencyKey, invitedEmail, "Member"),
            SendPostInvitation(client, idempotencyKey, invitedEmail, "Member"));

        responses.Should().Contain(r => r.StatusCode == HttpStatusCode.Created);
        responses.Should().OnlyContain(r =>
            r.StatusCode == HttpStatusCode.Created || r.StatusCode == HttpStatusCode.Conflict);

        var listBody = await client.GetStringAsync("/invitations", TestContext.Current.CancellationToken);
        CountOccurrences(listBody, invitedEmail).Should().Be(1);
    }

    /// <summary>
    /// The key is scoped to its caller: a second administrator using the same key value with a
    /// different body is not a key-reuse 422 and not a replay of the first administrator's
    /// response — it is a new request that creates its own invitation.
    /// </summary>
    [CoversRequirement("FR-020")]
    [Fact]
    public async Task Post_Invitations_SameKeyFromDifferentAdministrators_AreIndependentRequests()
    {
        var firstAdministrator = await Factory.SeedMemberAsync(Role.Administrator);
        var secondAdministrator = await Factory.SeedMemberAsync(Role.Administrator);
        using var firstClient = Factory.CreateClientFor(firstAdministrator);
        using var secondClient = Factory.CreateClientFor(secondAdministrator);

        var sharedKey = Guid.CreateVersion7().ToString();

        var first = await SendPostInvitation(firstClient, sharedKey, "from-first@example.com", "Member");
        var second = await SendPostInvitation(secondClient, sharedKey, "from-second@example.com", "Reader");

        first.StatusCode.Should().Be(HttpStatusCode.Created);
        second.StatusCode.Should().Be(HttpStatusCode.Created);
        GetIdempotencyReplayedHeaderValue(second).Should().NotBe("true");

        var listBody = await firstClient.GetStringAsync("/invitations", TestContext.Current.CancellationToken);
        listBody.Should().Contain("from-first@example.com").And.Contain("from-second@example.com");
    }

    private static async Task<HttpResponseMessage> SendPostInvitation(
        HttpClient client, string idempotencyKey, string email, string role)
    {
        using var request = new HttpRequestMessage(HttpMethod.Post, "/invitations")
        {
            Content = JsonContent.Create(new { email, role }),
        };
        request.Headers.Add("Idempotency-Key", idempotencyKey);

        return await client.SendAsync(request, TestContext.Current.CancellationToken);
    }

    private static string? GetIdempotencyReplayedHeaderValue(HttpResponseMessage response) =>
        response.Headers.TryGetValues("Idempotency-Replayed", out var values) ? values.FirstOrDefault() : null;

    private static int CountOccurrences(string haystack, string needle)
    {
        var count = 0;
        var index = 0;
        while ((index = haystack.IndexOf(needle, index, StringComparison.Ordinal)) != -1)
        {
            count++;
            index += needle.Length;
        }

        return count;
    }
}
