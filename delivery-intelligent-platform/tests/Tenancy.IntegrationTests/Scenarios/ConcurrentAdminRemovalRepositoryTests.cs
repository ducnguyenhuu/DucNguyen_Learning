using ArchitectureTests.Support;
using AwesomeAssertions;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Tenancy.Application.Abstractions;
using Tenancy.Domain.Abstractions;
using Tenancy.Domain.Memberships;
using Tenancy.Domain.Tenants;
using Tenancy.Domain.Users;
using Tenancy.Infrastructure.Persistence;
using Tenancy.IntegrationTests.Infrastructure;
using Xunit;

namespace Tenancy.IntegrationTests.Scenarios;

/// <summary>
/// T075: proves the repository-level mitigation for the last-administrator race
/// (<see cref="MembershipRepository.RemoveMembershipAsync"/>) actually holds under genuine
/// concurrency, exercising it directly against the real SQL Server Testcontainer rather than
/// through the (not-yet-existent, T079's job) HTTP <c>DELETE</c> route.
/// </summary>
/// <remarks>
/// <para>
/// <b>Relationship to <see cref="ConcurrentAdminRemovalTests"/> (T068).</b> T068's test fires the
/// same race through the HTTP layer and, until T079 lands, can only observe both requests failing
/// on the absent route — its assertion passes trivially today. This test mirrors T068's exact
/// concurrency technique (two request tasks constructed before either is awaited, both gated on a
/// shared <see cref="TaskCompletionSource"/> signal to maximize genuine overlap) but calls
/// <see cref="IMembershipRepository.RemoveMembershipAsync"/> directly, so it is the one test in
/// this codebase today that can actually prove T075's mitigation works, rather than merely
/// asserting the absence of two HTTP successes.
/// </para>
/// <para>
/// <b>What "the invariant holds" means here.</b> Admin A and Admin B are a tenant's only two
/// active administrators. Both calls attempt to remove the *other* administrator's membership,
/// genuinely concurrently. Exactly one of two outcomes is acceptable: (1) one call succeeds and
/// the other throws <see cref="DomainException"/> (the row lock serialized the two transactions,
/// and the second one's post-lock re-count correctly saw only one remaining administrator), or
/// (2) — far less likely given the row lock, but not ruled out by this assertion — both throw.
/// What must never happen is both succeeding, which would leave the tenant with zero
/// administrators. The test asserts on the ground truth (a direct DB read of the remaining active
/// administrator count), not on which call happened to win.
/// </para>
/// </remarks>
public sealed class ConcurrentAdminRemovalRepositoryTests : TenancyIntegrationTestBase
{

    public ConcurrentAdminRemovalRepositoryTests(SqlServerFixture sqlServerFixture, ApiFactory factory)
        : base(sqlServerFixture, factory)
    {
    }

    [CoversRequirement("FR-015")]
    [Fact]
    public async Task RemoveMembershipAsync_BothAdministrators_Concurrently_NeverLeavesZeroAdministrators()
    {
        await Factory.InitializeDatabaseAsync();
        var ct = TestContext.Current.CancellationToken;

        var (tenantId, adminAMembershipId, adminBMembershipId) = await SeedTwoAdministratorsOnlyTenantAsync(ct);

        // Shared start signal, mirroring ConcurrentAdminRemovalTests (T068): both calls block here
        // until both are constructed and started, maximizing the chance of genuine overlap rather
        // than incidental scheduling. Each call uses its own DI scope/DbContext instance, matching
        // how two real, independent HTTP requests would each get their own scoped DbContext.
        var start = new TaskCompletionSource();

        var removeATask = RemoveAsync(adminAMembershipId, start, ct);
        var removeBTask = RemoveAsync(adminBMembershipId, start, ct);

        start.SetResult();

        var results = await Task.WhenAll(removeATask, removeBTask);

        var succeededCount = results.Count(r => r.Succeeded);
        var refusedCount = results.Count(r => !r.Succeeded);

        // Target-spec property: both concurrent removals must never both succeed.
        succeededCount.Should().BeLessThanOrEqualTo(1);
        (succeededCount + refusedCount).Should().Be(2);

        var remainingAdministratorCount = await CountActiveAdministratorsAsync(tenantId, ct);
        remainingAdministratorCount.Should().BeGreaterThanOrEqualTo(1);
    }

    private async Task<RemovalResult> RemoveAsync(
        MembershipId membershipId,
        TaskCompletionSource start,
        CancellationToken ct)
    {
        await start.Task;

        using var scope = Factory.Services.CreateScope();
        var repository = scope.ServiceProvider.GetRequiredService<IMembershipRepository>();

        try
        {
            await repository.RemoveMembershipAsync(membershipId, ct);
            return new RemovalResult(Succeeded: true, Exception: null);
        }
        catch (DomainException ex)
        {
            return new RemovalResult(Succeeded: false, Exception: ex);
        }
    }

    private async Task<int> CountActiveAdministratorsAsync(TenantId tenantId, CancellationToken ct)
    {
        using var scope = Factory.Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<TenancyDbContext>();
        db.CurrentTenantId = tenantId;

        return await db.Memberships
            .IgnoreQueryFilters()
            .Where(m => m.TenantId == tenantId && m.Role == Role.Administrator && m.Status == MembershipStatus.Active)
            .CountAsync(ct);
    }

    /// <summary>
    /// Seeds a single tenant with exactly two active <see cref="Role.Administrator"/> members and
    /// no other members — the precise shape this race requires, following
    /// <see cref="ConcurrentAdminRemovalTests"/>'s local helper of the same shape.
    /// </summary>
    private async Task<(TenantId TenantId, MembershipId AdminAMembershipId, MembershipId AdminBMembershipId)>
        SeedTwoAdministratorsOnlyTenantAsync(CancellationToken ct)
    {
        using var scope = Factory.Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<TenancyDbContext>();

        var tenant = Tenant.Create("Two Administrators Only Tenant (Repository)");
        var adminA = User.Create(
            entraTenantId: Guid.CreateVersion7(),
            entraObjectId: Guid.CreateVersion7(),
            email: new EmailAddress("admin-a@two-admins-repo-tenant.example.com"));
        var adminB = User.Create(
            entraTenantId: Guid.CreateVersion7(),
            entraObjectId: Guid.CreateVersion7(),
            email: new EmailAddress("admin-b@two-admins-repo-tenant.example.com"));

        db.Tenants.Add(tenant);
        db.Users.Add(adminA);
        db.Users.Add(adminB);
        await db.SaveChangesAsync(ct);

        db.CurrentTenantId = tenant.Id;
        var membershipA = Membership.Create(tenant.Id, adminA.Id, Role.Administrator);
        var membershipB = Membership.Create(tenant.Id, adminB.Id, Role.Administrator);
        db.Memberships.Add(membershipA);
        db.Memberships.Add(membershipB);
        await db.SaveChangesAsync(ct);

        return (tenant.Id, membershipA.Id, membershipB.Id);
    }

    private sealed record RemovalResult(bool Succeeded, DomainException? Exception);
}
