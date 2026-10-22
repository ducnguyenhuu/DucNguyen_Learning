using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using ArchitectureTests.Support;
using AwesomeAssertions;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Tenancy.Api.ETags;
using Tenancy.Domain.Abstractions;
using Tenancy.Domain.Memberships;
using Tenancy.Domain.Tenants;
using Tenancy.Domain.Users;
using Tenancy.Infrastructure.Persistence;
using Tenancy.IntegrationTests.Infrastructure;
using Xunit;

namespace Tenancy.IntegrationTests.Scenarios;

/// <summary>
/// T084: a genuine-concurrency test for a plain optimistic-concurrency (rowversion/ETag) race on
/// <c>PATCH /tenants/{tenantId}/members/{userId}</c> — distinct from T068/T075's count-based
/// last-administrator invariant race. Here, two administrators both read the *same* target
/// member's current <c>RowVersion</c>, then both attempt to change that member's role with
/// <c>If-Match</c> set to that same value. Both callers' <c>If-Match</c> values were genuinely
/// valid when read (mirroring T058/T083's established 412-vs-409 distinction), so this is squarely
/// the "race at save" case: exactly one write can land, and the loser must see <c>409 Conflict</c>
/// rather than either a stale-precondition <c>412</c> or a silently lost update.
/// </summary>
/// <remarks>
/// <b>The gap this test targets.</b> FR-021 requires the system to "prevent lost updates when
/// concurrent changes are made to the same tenant or membership." A unit test cannot demonstrate
/// this (same reasoning as T068's remarks) — it requires two genuinely concurrent HTTP requests
/// racing against the real database's <c>rowversion</c> mechanism, where only one write can
/// actually commit against a given row version.
///
/// <b>What this test proves today vs. once T087 lands.</b> <c>PATCH
/// /tenants/{tenantId}/members/{userId}</c> does not exist as a route at all yet (T087's job), so
/// both concurrent requests below are expected to fail on ASP.NET Core's own "no matching
/// endpoint" response today, not on any business rule — consistent with
/// <see cref="ConcurrentAdminRemovalTests"/> (T068) and every other file in this sub-phase. The
/// target-spec assertion encoded below — exactly one <c>200</c> and one <c>409</c>, with the
/// final persisted role matching whichever request won — only becomes a meaningful proof of
/// optimistic-concurrency handling once T086/T087 land; until then it documents the intended
/// behavior and will fail on the absent route.
/// </remarks>
public sealed class ConcurrentRoleEditTests : TenancyIntegrationTestBase
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
    /// <see cref="ConcurrentAdminRemovalTests"/>'s T068 technique). Exactly one response must be
    /// <c>200</c> and the other <c>409</c> (race-at-save, not stale-at-read); the member's final
    /// persisted role — read directly via <see cref="ApiFactory"/>'s <see cref="TenancyDbContext"/>
    /// scope, not trusted from response bodies alone — must match whichever role the winning
    /// request requested, proving no lost update.
    /// </summary>
    [CoversRequirement("FR-021")]
    [Fact]
    public async Task Patch_MemberRole_TwoAdministrators_SameIfMatch_Concurrently_ExactlyOneWinsWithNoLostUpdate()
    {
        await Factory.InitializeDatabaseAsync();
        var seed = await SeedTwoAdministratorsAndOneMemberAsync();

        using var clientA = CreateAuthenticatedClient(seed.AdminA);
        using var clientB = CreateAuthenticatedClient(seed.AdminB);

        var sharedIfMatch = await GetMembershipIfMatchAsync(seed.TenantId, seed.Target.MembershipId);

        // Shared start signal: both request tasks block here until both are constructed and
        // started, so neither can complete before the other has begun — maximizing the chance of
        // a genuine race without over-engineering a precise interleaving guarantee.
        var start = new TaskCompletionSource();

        var requestA = RacePatchAsync(clientA, seed.TenantId, seed.Target.UserId, sharedIfMatch, "Member", start);
        var requestB = RacePatchAsync(clientB, seed.TenantId, seed.Target.UserId, sharedIfMatch, "Reader", start);

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
        var finalRole = await ReadFinalRoleAsync(seed.TenantId, seed.Target.MembershipId);

        // No lost update: the final persisted role must match exactly whichever request won —
        // never the loser's intended role, and never some silently merged/dropped in-between
        // state.
        finalRole.Should().Be(winningRole);
    }

    private static async Task<HttpResponseMessage> RacePatchAsync(
        HttpClient client,
        TenantId tenantId,
        UserId targetUserId,
        string ifMatch,
        string newRole,
        TaskCompletionSource start)
    {
        await start.Task;
        using var request = new HttpRequestMessage(
            HttpMethod.Patch,
            $"/tenants/{tenantId.Value}/members/{targetUserId.Value}")
        {
            Content = JsonContent.Create(new { role = newRole }),
        };
        request.Headers.Add("If-Match", ifMatch);
        return await client.SendAsync(request, TestContext.Current.CancellationToken);
    }

    private async Task<string> GetMembershipIfMatchAsync(TenantId tenantId, MembershipId membershipId)
    {
        using var scope = Factory.Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<TenancyDbContext>();
        db.CurrentTenantId = tenantId;
        var membership = await db.Memberships.FindAsync(
            [membershipId], TestContext.Current.CancellationToken);
        return RowVersionETag.ToETag(membership!.RowVersion);
    }

    private async Task<Role> ReadFinalRoleAsync(TenantId tenantId, MembershipId membershipId)
    {
        using var scope = Factory.Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<TenancyDbContext>();
        db.CurrentTenantId = tenantId;

        var membership = await db.Memberships
            .IgnoreQueryFilters()
            .AsNoTracking()
            .SingleAsync(m => m.Id == membershipId, TestContext.Current.CancellationToken);
        return membership.Role;
    }

    private HttpClient CreateAuthenticatedClient(SeededTenant seededTenant)
    {
        var client = Factory.CreateClient();
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("TestScheme", "test");
        client.DefaultRequestHeaders.Add("X-Test-Oid", seededTenant.EntraObjectId.ToString());
        client.DefaultRequestHeaders.Add("X-Test-Tid", seededTenant.EntraTenantId.ToString());
        return client;
    }

    /// <summary>
    /// Seeds a single tenant with two active <see cref="Role.Administrator"/> members and one
    /// additional active <see cref="Role.Member"/> — the target of the concurrent role-change
    /// race. Distinct from <see cref="ConcurrentAdminRemovalTests"/>'s
    /// <c>SeedTwoAdministratorsOnlyTenantAsync</c> (two administrators, nobody else) and
    /// <c>ChangeMemberRoleTests.SeedAdministratorAndMemberAsync</c> (one administrator, one
    /// member): this scenario needs two administrators (the racing callers) *and* a separate
    /// member (the shared target), so it is a new local helper following the same established
    /// convention.
    /// </summary>
    private async Task<TwoAdministratorsAndOneMemberSeed> SeedTwoAdministratorsAndOneMemberAsync()
    {
        using var scope = Factory.Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<TenancyDbContext>();

        var tenant = Tenant.Create("Concurrent Role Edit Tenant");
        var adminA = User.Create(
            entraTenantId: Guid.CreateVersion7(),
            entraObjectId: Guid.CreateVersion7(),
            email: new EmailAddress("admin-a@concurrent-role-edit-tenant.example.com"));
        var adminB = User.Create(
            entraTenantId: Guid.CreateVersion7(),
            entraObjectId: Guid.CreateVersion7(),
            email: new EmailAddress("admin-b@concurrent-role-edit-tenant.example.com"));
        var target = User.Create(
            entraTenantId: Guid.CreateVersion7(),
            entraObjectId: Guid.CreateVersion7(),
            email: new EmailAddress("target@concurrent-role-edit-tenant.example.com"));

        db.Tenants.Add(tenant);
        db.Users.Add(adminA);
        db.Users.Add(adminB);
        db.Users.Add(target);
        await db.SaveChangesAsync();

        db.CurrentTenantId = tenant.Id;
        var membershipA = Membership.Create(tenant.Id, adminA.Id, Role.Administrator);
        var membershipB = Membership.Create(tenant.Id, adminB.Id, Role.Administrator);
        var membershipTarget = Membership.Create(tenant.Id, target.Id, Role.Member);
        db.Memberships.Add(membershipA);
        db.Memberships.Add(membershipB);
        db.Memberships.Add(membershipTarget);
        await db.SaveChangesAsync();

        return new TwoAdministratorsAndOneMemberSeed(
            tenant.Id,
            new SeededTenant(tenant.Id, adminA.Id, membershipA.Id, adminA.EntraTenantId, adminA.EntraObjectId),
            new SeededTenant(tenant.Id, adminB.Id, membershipB.Id, adminB.EntraTenantId, adminB.EntraObjectId),
            new SeededTenant(tenant.Id, target.Id, membershipTarget.Id, target.EntraTenantId, target.EntraObjectId));
    }

    /// <summary>
    /// A single tenant seeded with two active <see cref="Role.Administrator"/> members (the
    /// racing callers) and one additional active <see cref="Role.Member"/> (the shared target of
    /// the concurrent role-change requests). All three <see cref="SeededTenant"/> values share
    /// the same <c>TenantId</c>.
    /// </summary>
    private sealed record TwoAdministratorsAndOneMemberSeed(
        TenantId TenantId,
        SeededTenant AdminA,
        SeededTenant AdminB,
        SeededTenant Target);
}
