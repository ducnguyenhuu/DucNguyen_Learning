using System.Net;
using System.Net.Http.Json;
using ArchitectureTests.Support;
using AwesomeAssertions;
using Identity.Domain.Abstractions;
using Identity.Domain.Invitations;
using Identity.IntegrationTests.Infrastructure;
using Xunit;

namespace Identity.IntegrationTests.Scenarios;

/// <summary>
/// Dedicated 404-family indistinguishability coverage for <c>POST /invitations/{token}/accept</c>.
/// Per <c>contracts/openapi.yaml</c>, a caller must not be able to tell from the response alone
/// <i>why</i> an invitation token didn't work. An unknown, expired, revoked or already-accepted
/// token all collapse into the identical <c>404 Not Found</c>, never a different code that would
/// let a caller probe token validity or invitation history — and none of them creates a
/// membership.
/// </summary>
/// <remarks>
/// <para>
/// <b>Scope boundary.</b> The one case deliberately kept <i>distinguishable</i> from this 404
/// family — a valid, unexpired token presented by the wrong identity, which the contract maps to
/// <c>403</c> because the token itself was genuine — is covered by
/// <see cref="InviteAndManageMembersTests"/>. This file covers every case where the token can
/// never succeed again.
/// </para>
/// <para>
/// <b>Real tokens, not placeholders.</b> Each invitation is seeded with the genuine hash of the
/// raw token the test then presents (<see cref="ApiFactory.SeedInvitationAsync"/>), so the
/// expired/revoked/accepted cases really resolve to a stored invitation and are refused for that
/// invitation's state — not merely because the token was never found.
/// </para>
/// </remarks>
public sealed class InvitationRefusalTests : IdentityIntegrationTestBase
{

    public InvitationRefusalTests(SqlServerFixture sqlServerFixture, ApiFactory factory)
        : base(sqlServerFixture, factory)
    {
    }

    /// <summary>
    /// An unknown token — one that was never issued/persisted at all — must yield 404, exactly
    /// like every other case in this file, so a caller cannot distinguish "never existed" from
    /// "existed but is no longer usable".
    /// </summary>
    [CoversRequirement("FR-013")]
    [Fact]
    public async Task Post_AcceptUnknownToken_Returns404()
    {
        await Factory.SeedMemberAsync(Role.Administrator);

        using var client = CreateInviteeClient("nobody@example.com");

        var response = await client.PostAsync(
            $"/invitations/{Guid.NewGuid()}/accept",
            content: null,
            TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.NotFound);
        await AssertCallerIsStillNotAMemberAsync(client);
    }

    /// <summary>
    /// A genuinely-persisted invitation whose expiry has already passed must yield 404, not a
    /// different code that would reveal the token once resolved to a real, time-expired
    /// invitation.
    /// </summary>
    [CoversRequirement("FR-013")]
    [Fact]
    public async Task Post_AcceptExpiredToken_Returns404()
    {
        await Factory.SeedMemberAsync(Role.Administrator);

        const string invitedEmail = "expired-invitee@example.com";
        const string rawToken = "refusal-expired-token";
        await Factory.SeedInvitationAsync(invitedEmail, Role.Member, rawToken, DateTimeOffset.UtcNow.AddDays(-1));

        using var client = CreateInviteeClient(invitedEmail);

        var response = await client.PostAsync(
            $"/invitations/{rawToken}/accept",
            content: null,
            TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.NotFound);
        await AssertCallerIsStillNotAMemberAsync(client);
    }

    /// <summary>
    /// A genuinely-persisted invitation that was explicitly revoked before anyone accepted it
    /// must yield 404, indistinguishable from a token that never existed.
    /// </summary>
    [CoversRequirement("FR-013")]
    [Fact]
    public async Task Post_AcceptRevokedToken_Returns404()
    {
        await Factory.SeedMemberAsync(Role.Administrator);

        const string invitedEmail = "revoked-invitee@example.com";
        const string rawToken = "refusal-revoked-token";
        await Factory.SeedInvitationAsync(
            invitedEmail, Role.Member, rawToken, DateTimeOffset.UtcNow.AddDays(7), InvitationStatus.Revoked);

        using var client = CreateInviteeClient(invitedEmail);

        var response = await client.PostAsync(
            $"/invitations/{rawToken}/accept",
            content: null,
            TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.NotFound);
        await AssertCallerIsStillNotAMemberAsync(client);
    }

    /// <summary>
    /// A genuinely-persisted invitation that has already been accepted once must refuse a second
    /// acceptance attempt with 404, not (for example) a 409 Conflict that would leak "this token
    /// was valid and used before".
    /// </summary>
    [CoversRequirement("FR-013")]
    [Fact]
    public async Task Post_AcceptAlreadyAcceptedToken_Returns404()
    {
        await Factory.SeedMemberAsync(Role.Administrator);

        const string invitedEmail = "already-accepted-invitee@example.com";
        const string rawToken = "refusal-already-accepted-token";
        await Factory.SeedInvitationAsync(
            invitedEmail, Role.Member, rawToken, DateTimeOffset.UtcNow.AddDays(7), InvitationStatus.Accepted);

        using var client = CreateInviteeClient(invitedEmail);

        var response = await client.PostAsync(
            $"/invitations/{rawToken}/accept",
            content: null,
            TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.NotFound);
        await AssertCallerIsStillNotAMemberAsync(client);
    }

    private HttpClient CreateInviteeClient(string invitedEmail)
    {
        var client = Factory.CreateClientForStranger();
        client.DefaultRequestHeaders.Add("X-Test-Email", invitedEmail);
        return client;
    }

    /// <summary>A refused acceptance must not have granted the caller any membership.</summary>
    private static async Task AssertCallerIsStillNotAMemberAsync(HttpClient client)
    {
        var me = await client.GetFromJsonAsync<MeResponse>("/me", TestContext.Current.CancellationToken);
        me!.Role.Should().BeNull();
    }

    private sealed record MeResponse(Guid UserId, string Email, string? Role);
}
