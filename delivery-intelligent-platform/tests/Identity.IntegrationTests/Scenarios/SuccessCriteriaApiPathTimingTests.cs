using System.Diagnostics;
using System.Net;
using System.Net.Http.Json;
using AwesomeAssertions;
using Identity.Domain.Abstractions;
using Identity.IntegrationTests.Infrastructure;
using Xunit;

namespace Identity.IntegrationTests.Scenarios;

/// <summary>
/// Real, measured wall-clock timing for the mechanical API-path sequence a UI would
/// eventually drive for SC-001 and SC-002, per plan.md's Complexity Tracking framing.
/// </summary>
/// <remarks>
/// <para>
/// SC-001 ("A new administrator can go from first sign-in to a created tenant with one colleague
/// invited in under 5 minutes without documentation or assistance") and SC-002 ("An invited
/// colleague can accept an invitation and reach tenant data in under 2 minutes from opening the
/// invitation") both describe a <b>human using a UI without reading docs</b>. This slice is
/// API-only — there is no UI. What this test <b>can</b> measure is the mechanical sequence of
/// HTTP calls a UI would eventually drive, against the real running API: real EF Core, real SQL
/// Server Testcontainer, real ASP.NET Core pipeline — everything except a real Entra token
/// (<see cref="TestAuthHandler"/> stands in, per this suite's established Tier 1 convention).
/// </para>
/// <para>
/// <b>This is an API-path timing proxy, not a literal SC-001/SC-002 pass/fail.</b> The
/// human/no-documentation/UI dimension of both criteria remains genuinely unverified until a UI
/// exists — this test does not, and cannot, claim otherwise. The assertions below are a
/// regression guard (the mechanical sequence should stay comfortably under the human-facing
/// budget) with generous headroom, not a certification of the human-facing criteria.
/// </para>
/// </remarks>
public sealed class SuccessCriteriaApiPathTimingTests : IdentityIntegrationTestBase
{
    public SuccessCriteriaApiPathTimingTests(SqlServerFixture sqlServerFixture, ApiFactory factory)
        : base(sqlServerFixture, factory)
    {
    }

    /// <summary>
    /// SC-001's API-path proxy (ADR-025 reads "a created tenant" as "the organization, with its
    /// first administrator"): a new caller -&gt; <c>POST /members/bootstrap</c> -&gt;
    /// <c>POST /invitations</c> (invite one colleague). Budget of 30s is deliberately generous
    /// relative to SC-001's 5-minute human budget — this guards against gross regression, not
    /// against the human-facing criterion itself.
    /// </summary>
    [Fact]
    public async Task ApiPath_Bootstrap_ThenInviteColleague_CompletesWellUnderScOneBudget()
    {
        using var client = Factory.CreateClientForStranger();

        var stopwatch = Stopwatch.StartNew();

        var bootstrapResponse = await client.PostAsync(
            "/members/bootstrap", content: null, TestContext.Current.CancellationToken);
        bootstrapResponse.StatusCode.Should().Be(HttpStatusCode.Created);

        client.DefaultRequestHeaders.Add("Idempotency-Key", Guid.NewGuid().ToString());
        var inviteResponse = await client.PostAsJsonAsync(
            "/invitations",
            new { email = "colleague@sc001-timing.example.com", role = "Member" },
            TestContext.Current.CancellationToken);
        inviteResponse.StatusCode.Should().Be(HttpStatusCode.Created);

        stopwatch.Stop();

        TestContext.Current.SendDiagnosticMessage(
            $"SC-001 API-path timing (bootstrap + invite colleague): {stopwatch.Elapsed.TotalSeconds:F3}s");

        stopwatch.Elapsed.Should().BeLessThan(
            TimeSpan.FromSeconds(30),
            "the mechanical API-path sequence should stay well under SC-001's 5-minute human-facing budget; " +
            "this is a regression guard, not a certification of the human/no-documentation dimension");
    }

    /// <summary>
    /// SC-002's API-path proxy: the invited colleague -&gt;
    /// <c>POST /invitations/{token}/accept</c> -&gt; <c>GET /me</c> (reach the organization as a
    /// member). Budget of 15s is deliberately generous relative to SC-002's 2-minute human budget.
    /// </summary>
    [Fact]
    public async Task ApiPath_AcceptInvitation_ThenGetMe_CompletesWellUnderScTwoBudget()
    {
        var administrator = await Factory.SeedMemberAsync(Role.Administrator);
        using var adminClient = Factory.CreateClientFor(administrator);
        adminClient.DefaultRequestHeaders.Add("Idempotency-Key", Guid.NewGuid().ToString());

        const string invitedEmail = "invitee@sc002-timing.example.com";
        var inviteResponse = await adminClient.PostAsJsonAsync(
            "/invitations",
            new { email = invitedEmail, role = "Member" },
            TestContext.Current.CancellationToken);
        inviteResponse.StatusCode.Should().Be(HttpStatusCode.Created);
        var inviteBody = await inviteResponse.Content.ReadFromJsonAsync<InvitationResponse>(
            TestContext.Current.CancellationToken);
        inviteBody.Should().NotBeNull();
        inviteBody!.Token.Should().NotBeNullOrWhiteSpace();

        using var inviteeClient = Factory.CreateClientForStranger();
        inviteeClient.DefaultRequestHeaders.Add("X-Test-Email", invitedEmail);

        // Only the invitee's own sequence (accept -> reach the organization) is timed, per
        // SC-002's wording ("from opening the invitation") -- the administrator's invite above is
        // SC-001's concern, not SC-002's.
        var stopwatch = Stopwatch.StartNew();

        var acceptResponse = await inviteeClient.PostAsync(
            $"/invitations/{inviteBody.Token}/accept",
            content: null,
            TestContext.Current.CancellationToken);
        acceptResponse.StatusCode.Should().Be(HttpStatusCode.OK);

        var me = await inviteeClient.GetFromJsonAsync<MeResponse>("/me", TestContext.Current.CancellationToken);
        me!.Role.Should().Be("Member");

        stopwatch.Stop();

        TestContext.Current.SendDiagnosticMessage(
            $"SC-002 API-path timing (accept invitation + GET /me): {stopwatch.Elapsed.TotalSeconds:F3}s");

        stopwatch.Elapsed.Should().BeLessThan(
            TimeSpan.FromSeconds(15),
            "the mechanical API-path sequence should stay well under SC-002's 2-minute human-facing budget; " +
            "this is a regression guard, not a certification of the human/no-documentation dimension");
    }

    private sealed record InvitationResponse(string Token);

    private sealed record MeResponse(Guid UserId, string Email, string? Role);
}
