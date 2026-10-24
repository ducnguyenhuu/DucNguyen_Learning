using ArchitectureTests.Support;
using AwesomeAssertions;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Identity.Application.Abstractions;
using Identity.Domain.Abstractions;
using Identity.Domain.Memberships;
using Identity.Infrastructure.Persistence;
using Identity.IntegrationTests.Infrastructure;
using Xunit;

namespace Identity.IntegrationTests.Scenarios;

/// <summary>
/// Proves the repository-level mitigation for the last-administrator race
/// (<see cref="MembershipRepository.RemoveMembershipAsync"/>, serialized by the
/// <c>Identity.Memberships.Administrators</c> application lock) holds under genuine concurrency,
/// exercising it directly against the real SQL Server Testcontainer, one layer below the HTTP
/// <c>DELETE</c> route.
/// </summary>
/// <remarks>
/// <para>
/// <b>Relationship to <see cref="ConcurrentAdminRemovalTests"/>.</b> That test fires the same race
/// through HTTP. This one mirrors its concurrency technique (two tasks constructed before either
/// is awaited, both gated on a shared <see cref="TaskCompletionSource"/> signal to maximize
/// genuine overlap) but calls <see cref="IMembershipRepository.RemoveMembershipAsync"/> directly,
/// so a failure here points at the lock itself rather than at the endpoint around it.
/// </para>
/// <para>
/// <b>What "the invariant holds" means here.</b> Admin A and Admin B are the organization's only two
/// active administrators. Both calls attempt to remove the *other* administrator's membership,
/// genuinely concurrently. Exactly one of two outcomes is acceptable: (1) one call succeeds and
/// the other throws <see cref="DomainException"/> (the application lock serialized the two transactions,
/// and the second one's post-lock re-count correctly saw only one remaining administrator), or
/// (2) — far less likely given the lock, but not ruled out by this assertion — both throw.
/// What must never happen is both succeeding, which would leave the organization with zero
/// administrators. The test asserts on the ground truth (a direct DB read of the remaining active
/// administrator count), not on which call happened to win.
/// </para>
/// </remarks>
public sealed class ConcurrentAdminRemovalRepositoryTests : IdentityIntegrationTestBase
{

    public ConcurrentAdminRemovalRepositoryTests(SqlServerFixture sqlServerFixture, ApiFactory factory)
        : base(sqlServerFixture, factory)
    {
    }

    [CoversRequirement("FR-015")]
    [Fact]
    public async Task RemoveMembershipAsync_BothAdministrators_Concurrently_NeverLeavesZeroAdministrators()
    {
        var ct = TestContext.Current.CancellationToken;

        var adminAMembershipId = (await Factory.SeedMemberAsync(Role.Administrator)).MembershipId;
        var adminBMembershipId = (await Factory.SeedMemberAsync(Role.Administrator)).MembershipId;

        // Shared start signal, mirroring ConcurrentAdminRemovalTests: both calls block here
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

        var remainingAdministratorCount = await CountActiveAdministratorsAsync(ct);
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

    private async Task<int> CountActiveAdministratorsAsync(CancellationToken ct)
    {
        using var scope = Factory.Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<IdentityDbContext>();

        return await db.Memberships
            .Where(m => m.Role == Role.Administrator && m.Status == MembershipStatus.Active)
            .CountAsync(ct);
    }

    private sealed record RemovalResult(bool Succeeded, DomainException? Exception);
}
