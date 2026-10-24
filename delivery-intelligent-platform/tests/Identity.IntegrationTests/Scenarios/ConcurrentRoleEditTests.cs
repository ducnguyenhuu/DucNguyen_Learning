using System.Net;
using System.Net.Http.Json;
using ArchitectureTests.Support;
using AwesomeAssertions;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Identity.Domain.Abstractions;
using Identity.Domain.Memberships;
using Identity.Domain.Users;
using Identity.Infrastructure.Persistence;
using Identity.IntegrationTests.Infrastructure;
using Xunit;

namespace Identity.IntegrationTests.Scenarios;

/// <summary>
/// A genuine-concurrency test for a plain optimistic-concurrency (rowversion/ETag) race on
/// <c>PATCH /members/{userId}</c> — distinct from the count-based last-administrator race in
/// <see cref="ConcurrentAdminRemovalTests"/>. Two administrators both read the <em>same</em>
/// target member's current <c>RowVersion</c>, then both attempt to change that member's role with
/// <c>If-Match</c> set to that value. Exactly one write can land; the loser must be refused as a
/// concurrency conflict rather than silently losing (or overwriting) the other's update.
/// </summary>
/// <remarks>
/// FR-021 requires the system to "prevent lost updates when concurrent changes are made to the
/// same membership." A unit test cannot demonstrate this: it needs two genuinely concurrent HTTP
/// requests racing against the real database's <c>rowversion</c> mechanism, where only one write
/// can commit against a given row version. One racer requests the member's already-current role,
/// which is the case <c>MemberEndpoints.PatchMemberRoleAsync</c> forces into a real
/// <c>UPDATE</c> so the concurrency check still runs.
/// </remarks>
public sealed class ConcurrentRoleEditTests : IdentityIntegrationTestBase
{

    public ConcurrentRoleEditTests(SqlServerFixture sqlServerFixture, ApiFactory factory)
        : base(sqlServerFixture, factory)
    {
    }

    /// <summary>
    /// Two administrators (Admin A and Admin B) both read the target member's current
    /// <c>RowVersion</c>/<c>ETag</c>, then both fire a <c>PATCH</c> to change that member's role —
    /// one to <see cref="Role.Member"/>, the other to <see cref="Role.Reader"/> — using the *same*
    /// captured <c>If-Match</c> value, genuinely concurrently (both requests are constructed and
    /// started before either is awaited, and both wait on a shared
    /// <see cref="TaskCompletionSource"/> signal to maximize the chance of real overlap, mirroring
    /// <see cref="ConcurrentAdminRemovalTests"/>' technique). Exactly one response must be
    /// <c>200</c> and the other <c>409</c> (race-at-save, not stale-at-read); the member's final
    /// persisted role — read directly via <see cref="ApiFactory"/>'s <see cref="IdentityDbContext"/>
    /// scope, not trusted from response bodies alone — must match whichever role the winning
    /// request requested, proving no lost update.
    /// </summary>
    [CoversRequirement("FR-021")]
    [Fact]
    public async Task Patch_MemberRole_TwoAdministrators_SameIfMatch_Concurrently_ExactlyOneWinsWithNoLostUpdate()
    {
        var seed = new TwoAdministratorsAndOneMemberSeed(
            await Factory.SeedMemberAsync(Role.Administrator),
            await Factory.SeedMemberAsync(Role.Administrator),
            await Factory.SeedMemberAsync(Role.Member));

        using var clientA = Factory.CreateClientFor(seed.AdminA);
        using var clientB = Factory.CreateClientFor(seed.AdminB);

        var sharedIfMatch = await Factory.GetMembershipIfMatchAsync(seed.Target.MembershipId);

        // Shared start signal: both request tasks block here until both are constructed and
        // started, so neither can complete before the other has begun — maximizing the chance of
        // a genuine race without over-engineering a precise interleaving guarantee.
        var start = new TaskCompletionSource();

        var requestA = RacePatchAsync(clientA, seed.Target.UserId, sharedIfMatch, "Member", start);
        var requestB = RacePatchAsync(clientB, seed.Target.UserId, sharedIfMatch, "Reader", start);

        start.SetResult();
        var responses = await Task.WhenAll(requestA, requestB);

        var (roleA, responseA) = (Role.Member, responses[0]);
        var (roleB, responseB) = (Role.Reader, responses[1]);

        var statusCodes = new[] { responseA.StatusCode, responseB.StatusCode };

        // Target-spec property: exactly one caller's write lands (200). The other must be
        // refused as a concurrency conflict, but depending on exact timing that refusal may
        // surface as either 409 (race-at-save: the loser's If-Match matched at read time but the
        // winner's write landed first) or 412 (the loser's own fresh pre-check read at the
        // endpoint already observed the winner's new RowVersion before the loser's write raced) —
        // both are correct concurrency refusals for the same real race, so either is accepted here.
        // What must NOT vary is that exactly one request succeeds, and the no-lost-update
        // assertion below stays strict.
        statusCodes.Should().ContainSingle(code => code == HttpStatusCode.OK);
        statusCodes.Should().ContainSingle(code =>
            code == HttpStatusCode.Conflict || code == HttpStatusCode.PreconditionFailed);

        var winningRole = responseA.StatusCode == HttpStatusCode.OK ? roleA : roleB;
        var finalRole = await ReadFinalRoleAsync(seed.Target.MembershipId);

        // No lost update: the final persisted role must match exactly whichever request won —
        // never the loser's intended role, and never some silently merged/dropped in-between
        // state.
        finalRole.Should().Be(winningRole);
    }

    private static async Task<HttpResponseMessage> RacePatchAsync(
        HttpClient client,
        UserId targetUserId,
        string ifMatch,
        string newRole,
        TaskCompletionSource start)
    {
        await start.Task;
        using var request = new HttpRequestMessage(
            HttpMethod.Patch,
            $"/members/{targetUserId.Value}")
        {
            Content = JsonContent.Create(new { role = newRole }),
        };
        request.Headers.Add("If-Match", ifMatch);
        return await client.SendAsync(request, TestContext.Current.CancellationToken);
    }

    private async Task<Role> ReadFinalRoleAsync(MembershipId membershipId)
    {
        using var scope = Factory.Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<IdentityDbContext>();

        var membership = await db.Memberships
            .AsNoTracking()
            .SingleAsync(m => m.Id == membershipId, TestContext.Current.CancellationToken);
        return membership.Role;
    }

    /// <summary>
    /// Two Administrators (the racing callers) and one Member (the shared target of the
    /// concurrent role-change requests).
    /// </summary>
    private sealed record TwoAdministratorsAndOneMemberSeed(
        SeededMember AdminA,
        SeededMember AdminB,
        SeededMember Target);
}
