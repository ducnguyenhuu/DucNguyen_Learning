using System.Net;
using System.Net.Http.Headers;
using ArchitectureTests.Support;
using AwesomeAssertions;
using Identity.Domain.Abstractions;
using Identity.IntegrationTests.Infrastructure;
using Xunit;

namespace Identity.IntegrationTests.Scenarios;

/// <summary>
/// Documents the accepted revocation-staleness trade-off from spec.md's Assumption 7 and FR-016:
/// "Credentials are short-lived enough that revoked access ends within one hour, satisfying
/// FR-016 without per-request revocation checks." This file proves <b>both halves</b> of that
/// trade-off, not just the convenient one.
/// </summary>
/// <remarks>
/// <para>
/// <b>Half 1 (instantaneous):</b> once a member is removed, their next request to a member-only
/// route is refused immediately — not because the token became stale, but because
/// <c>MembershipResolutionFilter</c> checks the current <c>MembershipStatus</c> in the database on
/// every request, never the token's claims. A removed member gets exactly the 403 a caller who
/// was never a member gets.
/// </para>
/// <para>
/// <b>Half 2 (deliberately not instantaneous):</b> a token already issued <i>before</i> removal,
/// and not yet expired, is not rejected on token grounds. The system keeps no token blocklist;
/// FR-016 is satisfied by the token's own short expiry. This half uses
/// <see cref="SignedTokenHarness"/> — a real, RSA-signed JWT through the genuine <c>JwtBearer</c>
/// pipeline — because only a real signed token can prove "the token itself was not the reason for
/// any refusal". <see cref="TestAuthHandler"/> never exercises token validation, so a Tier-1 test
/// could not tell "the token wasn't blocklisted" from "no token validation happened at all".
/// </para>
/// <para>
/// The removed member is seeded as an <see cref="Role.Administrator"/> so the probe route
/// (<c>GET /members</c>) genuinely succeeds for them before removal; any refusal afterwards can
/// then only be the removal taking effect.
/// </para>
/// </remarks>
public sealed class RevocationWindowTests : IdentityIntegrationTestBase
{
    public RevocationWindowTests(SqlServerFixture sqlServerFixture, ApiFactory factory)
        : base(sqlServerFixture, factory)
    {
    }

    /// <summary>
    /// Half 1: after removal, a fresh authenticated request from the removed member is refused
    /// with 403, byte-for-byte identical (status and body) to the refusal a caller who was never
    /// a member gets for the same request — the refusal says "not a member", nothing about
    /// having been one.
    /// </summary>
    [CoversRequirement("FR-016")]
    [Fact]
    public async Task RemovedMember_FreshRequest_IsRefused_AndIndistinguishableFromNeverAMember()
    {
        var administrator = await Factory.SeedMemberAsync(Role.Administrator);
        var removedMember = await Factory.SeedMemberAsync(Role.Administrator);

        using var removedMemberClient = Factory.CreateClientFor(removedMember);
        var beforeRemoval = await removedMemberClient.GetAsync("/members", TestContext.Current.CancellationToken);
        beforeRemoval.StatusCode.Should().Be(HttpStatusCode.OK);

        await RemoveAsync(administrator, removedMember);

        var removedMemberResponse = await removedMemberClient.GetAsync("/members", TestContext.Current.CancellationToken);

        using var strangerClient = Factory.CreateClientForStranger();
        var strangerResponse = await strangerClient.GetAsync("/members", TestContext.Current.CancellationToken);

        removedMemberResponse.StatusCode.Should().Be(HttpStatusCode.Forbidden);
        removedMemberResponse.StatusCode.Should().Be(strangerResponse.StatusCode);

        var removedMemberBody = await removedMemberResponse.Content.ReadAsStringAsync(TestContext.Current.CancellationToken);
        var strangerBody = await strangerResponse.Content.ReadAsStringAsync(TestContext.Current.CancellationToken);
        removedMemberBody.Should().Be(strangerBody);
    }

    /// <summary>
    /// Half 2: a token minted <b>before</b> removal, still cryptographically unexpired, is
    /// replayed <b>after</b> removal. It must never come back <c>401 Unauthorized</c> (the status
    /// openapi.yaml reserves for "no token, or a token that fails validation"); the refusal is
    /// the membership check's 403, a membership problem rather than a token problem.
    /// </summary>
    [CoversRequirement("FR-016")]
    [Fact]
    public async Task AlreadyIssuedToken_ReplayedAfterRemoval_IsNotRejectedOnTokenGrounds()
    {
        var administrator = await Factory.SeedMemberAsync(Role.Administrator);
        var removedMember = await Factory.SeedMemberAsync(Role.Administrator);

        var memberToken = Factory.TokenHarness.MintToken(
            tid: removedMember.EntraTenantId,
            oid: removedMember.EntraObjectId,
            audience: ApiFactory.ExpectedAudience,
            issuer: ApiFactory.ExpectedIssuer);

        using var replayClient = Factory.CreateClient();
        replayClient.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", memberToken);

        var beforeRemoval = await replayClient.GetAsync("/members", TestContext.Current.CancellationToken);
        beforeRemoval.StatusCode.Should().Be(HttpStatusCode.OK, "the minted token is genuinely valid");

        await RemoveAsync(administrator, removedMember);

        var replayResponse = await replayClient.GetAsync("/members", TestContext.Current.CancellationToken);

        replayResponse.StatusCode.Should().NotBe(HttpStatusCode.Unauthorized);
        replayResponse.StatusCode.Should().Be(HttpStatusCode.Forbidden);
    }

    private async Task RemoveAsync(SeededMember administrator, SeededMember target)
    {
        using var adminClient = Factory.CreateClientFor(administrator);
        using var deleteRequest = new HttpRequestMessage(HttpMethod.Delete, $"/members/{target.UserId.Value}");
        deleteRequest.Headers.TryAddWithoutValidation(
            "If-Match", await Factory.GetMembershipIfMatchAsync(target.MembershipId));

        var deleteResponse = await adminClient.SendAsync(deleteRequest, TestContext.Current.CancellationToken);
        deleteResponse.StatusCode.Should().Be(HttpStatusCode.NoContent);
    }
}
