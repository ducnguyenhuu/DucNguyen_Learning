using System.Net.Http.Headers;
using ArchitectureTests.Support;
using AwesomeAssertions;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Identity.Domain.Abstractions;
using Identity.Domain.Memberships;
using Identity.Domain.Tenants;
using Identity.Domain.Users;
using Identity.Infrastructure.Persistence;
using Identity.IntegrationTests.Infrastructure;
using Xunit;

namespace Identity.IntegrationTests.Scenarios;

/// <summary>
/// T068: a genuine-concurrency test for the last-administrator invariant, distinct from T067's
/// unit-level guard and T074's future domain-level guard. Neither of those can demonstrate this
/// gap because it only manifests when two writes to the *same* tenant's administrator count race
/// against each other in real, overlapping database transactions.
/// </summary>
/// <remarks>
/// <b>The gap this test targets.</b> data-model.md (section on the last-administrator rule)
/// states it plainly: "two concurrent transactions each removing a different administrator, when
/// exactly two exist, could both observe a count of 2 and both succeed under
/// <c>READ COMMITTED</c> — leaving zero." That is exactly the scenario below: Admin A and Admin B
/// are the tenant's only two administrators; A removes B and B removes A, genuinely
/// simultaneously. Under plain <c>READ COMMITTED</c> with no additional protection, both counts
/// can be read as "2" before either write commits, so both removals could succeed and the tenant
/// is left with zero administrators — the exact outcome the last-administrator rule exists to
/// prevent.
///
/// <b>Why this can't be a unit test.</b> A unit test calls the domain operation once, synchronously,
/// with a count it's handed — it cannot make two real database transactions overlap in time. Only
/// a real concurrency scenario against a live database (here, the SQL Server Testcontainer behind
/// <see cref="ApiFactory"/>) can prove whether the eventual guard survives an actual race, not just
/// a single call.
///
/// <b>What "the fix" will look like (T075, not implemented here).</b> Per tasks.md's T075: "count
/// administrators and write the membership change in one transaction at <c>SERIALIZABLE</c>, or
/// take the tenant row lock before counting." This test does not implement either mitigation — it
/// only proves the gap exists today and will re-run unchanged once T075 lands, at which point its
/// assertion becomes meaningful rather than trivially satisfied by an absent route.
///
/// <b>What this test proves today vs. once T075/T079 land.</b> The member-removal endpoint
/// (<c>DELETE /tenants/{tenantId}/members/{userId}</c>) does not exist yet — T079 adds it, and
/// T075 adds the transactional protection this scenario is designed to exercise. Today, both
/// concurrent requests are expected to fail on ASP.NET Core's own absent-route response, not on
/// any business rule — consistent with every other test file in this sub-phase (see
/// <see cref="InviteAndManageMembersTests"/>'s remarks for the established precedent). The
/// target-spec assertion encoded below — that the tenant never ends up with zero administrators —
/// only becomes a meaningful proof of T075's mitigation once T075 and T079 both exist; until then
/// it is trivially true because neither removal can succeed at all.
/// </remarks>
public sealed class ConcurrentAdminRemovalTests : IdentityIntegrationTestBase
{

    public ConcurrentAdminRemovalTests(SqlServerFixture sqlServerFixture, ApiFactory factory)
        : base(sqlServerFixture, factory)
    {
    }

    /// <summary>
    /// Admin A and Admin B are the tenant's only two administrators. Both fire a
    /// <c>DELETE</c> targeting the *other* administrator's membership, genuinely
    /// concurrently (both requests are constructed and started before either is awaited, and
    /// both wait on a shared <see cref="TaskCompletionSource"/> signal to maximize the chance of
    /// real overlap rather than incidental scheduling). Regardless of which HTTP status codes
    /// come back, the tenant must never end up with zero active administrators — checked by a
    /// direct DB read through <see cref="ApiFactory"/>'s <see cref="IdentityDbContext"/>, not by
    /// trusting response codes alone, since today's absent-route failures and tomorrow's genuine
    /// race outcomes both need the same ground-truth check.
    /// </summary>
    [CoversRequirement("FR-015")]
    [Fact]
    public async Task Delete_BothAdministrators_Concurrently_NeverLeavesZeroAdministrators()
    {
        await Factory.InitializeDatabaseAsync();
        var seed = await SeedTwoAdministratorsOnlyTenantAsync();

        using var clientA = CreateAuthenticatedClient(seed.AdminA);
        using var clientB = CreateAuthenticatedClient(seed.AdminB);

        // Shared start signal: both request tasks block here until both are constructed and
        // started, so neither can complete before the other has begun — maximizing the chance of
        // a genuine race without over-engineering a precise interleaving guarantee.
        var start = new TaskCompletionSource();

        var requestA = RaceDeleteAsync(clientA, seed.TenantId, seed.AdminB.UserId, start);
        var requestB = RaceDeleteAsync(clientB, seed.TenantId, seed.AdminA.UserId, start);

        start.SetResult();
        await Task.WhenAll(requestA, requestB);

        var remainingAdministratorCount = await CountActiveAdministratorsAsync(seed.TenantId);

        // Target-spec property: at most one removal may ever succeed; the tenant must never be
        // left administrator-less. Today, neither request can succeed at all (absent route), so
        // this passes trivially. Once T075 (transactional protection) and T079 (the endpoint
        // itself) land, this becomes the real proof that the SERIALIZABLE-or-row-lock mitigation
        // survives an actual concurrent race, not just reasoning about it.
        remainingAdministratorCount.Should().BeGreaterThanOrEqualTo(1);
    }

    private static async Task<HttpResponseMessage> RaceDeleteAsync(
        HttpClient client,
        TenantId tenantId,
        UserId targetUserId,
        TaskCompletionSource start)
    {
        await start.Task;
        return await client.DeleteAsync(
            $"/tenants/{tenantId.Value}/members/{targetUserId.Value}",
            TestContext.Current.CancellationToken);
    }

    private async Task<int> CountActiveAdministratorsAsync(TenantId tenantId)
    {
        using var scope = Factory.Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<IdentityDbContext>();
        db.CurrentTenantId = tenantId;

        return await db.Memberships
            .IgnoreQueryFilters()
            .Where(m => m.TenantId == tenantId && m.Role == Role.Administrator && m.Status == MembershipStatus.Active)
            .CountAsync(TestContext.Current.CancellationToken);
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
    /// Seeds a single tenant with exactly two active <see cref="Role.Administrator"/> members and
    /// no other members — the precise shape T068's race requires. Distinct from T063's local
    /// helpers (<c>SeedAdministratorAndMemberAsync</c> seeds one admin + one non-admin member;
    /// <c>SeedSoleAdministratorTenantAsync</c> seeds only one administrator); neither fits "two
    /// administrators, nobody else", so this is a new minimal helper following the same
    /// established local-helper convention.
    /// </summary>
    private async Task<TwoAdministratorsOnlySeed> SeedTwoAdministratorsOnlyTenantAsync()
    {
        using var scope = Factory.Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<IdentityDbContext>();

        var tenant = Tenant.Create("Two Administrators Only Tenant");
        var adminA = User.Create(
            entraTenantId: Guid.CreateVersion7(),
            entraObjectId: Guid.CreateVersion7(),
            email: new EmailAddress("admin-a@two-admins-tenant.example.com"));
        var adminB = User.Create(
            entraTenantId: Guid.CreateVersion7(),
            entraObjectId: Guid.CreateVersion7(),
            email: new EmailAddress("admin-b@two-admins-tenant.example.com"));

        db.Tenants.Add(tenant);
        db.Users.Add(adminA);
        db.Users.Add(adminB);
        await db.SaveChangesAsync();

        db.CurrentTenantId = tenant.Id;
        var membershipA = Membership.Create(tenant.Id, adminA.Id, Role.Administrator);
        var membershipB = Membership.Create(tenant.Id, adminB.Id, Role.Administrator);
        db.Memberships.Add(membershipA);
        db.Memberships.Add(membershipB);
        await db.SaveChangesAsync();

        return new TwoAdministratorsOnlySeed(
            tenant.Id,
            new SeededTenant(tenant.Id, adminA.Id, membershipA.Id, adminA.EntraTenantId, adminA.EntraObjectId),
            new SeededTenant(tenant.Id, adminB.Id, membershipB.Id, adminB.EntraTenantId, adminB.EntraObjectId));
    }

    /// <summary>
    /// A single tenant seeded with exactly two active <see cref="Role.Administrator"/> members and
    /// no other members. Both <see cref="SeededTenant"/> values share the same <c>TenantId</c>.
    /// </summary>
    private sealed record TwoAdministratorsOnlySeed(TenantId TenantId, SeededTenant AdminA, SeededTenant AdminB);
}
