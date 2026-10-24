using System.Net;
using ArchitectureTests.Support;
using AwesomeAssertions;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Identity.Domain.Abstractions;
using Identity.Domain.Memberships;
using Identity.Infrastructure.Persistence;
using Identity.IntegrationTests.Infrastructure;
using Xunit;

namespace Identity.IntegrationTests.Scenarios;

/// <summary>
/// A genuine-concurrency test, through HTTP, for the last-administrator invariant (FR-015). The
/// unit-level guard (<see cref="OrganizationAdministration"/>) cannot demonstrate this gap,
/// because it only manifests when two writes to the organization's administrator count race in
/// real, overlapping database transactions.
/// </summary>
/// <remarks>
/// <para>
/// <b>The gap.</b> data-model.md states it plainly: "two concurrent transactions each removing a
/// different administrator, when exactly two exist, could both observe a count of 2 and both
/// succeed under <c>READ COMMITTED</c> — leaving zero." That is the scenario below: Admin A and
/// Admin B are the organization's only two administrators; A removes B and B removes A, genuinely
/// simultaneously.
/// </para>
/// <para>
/// <b>The mitigation under test.</b> <c>MembershipRepository.RemoveMembershipAsync</c> takes the
/// transaction-scoped application lock <c>Identity.Memberships.Administrators</c> before counting,
/// so the second removal waits for the first to commit and then re-counts against the post-commit
/// state. Both requests carry a current <c>If-Match</c>, so both pass the endpoint's 412
/// pre-check and genuinely reach the guarded write; the ground truth is a direct database read,
/// not the response codes.
/// </para>
/// <para>
/// <see cref="ConcurrentAdminRemovalRepositoryTests"/> runs the same race one layer down, directly
/// against the repository.
/// </para>
/// </remarks>
public sealed class ConcurrentAdminRemovalTests : IdentityIntegrationTestBase
{
    public ConcurrentAdminRemovalTests(SqlServerFixture sqlServerFixture, ApiFactory factory)
        : base(sqlServerFixture, factory)
    {
    }

    /// <summary>
    /// Both administrators fire a <c>DELETE</c> at the other's membership, both started before
    /// either is awaited and gated on a shared <see cref="TaskCompletionSource"/> to maximize real
    /// overlap. At most one may succeed (204); the other is refused (409); and the organization
    /// must never be left with zero active administrators.
    /// </summary>
    [CoversRequirement("FR-015")]
    [Fact]
    public async Task Delete_BothAdministrators_Concurrently_NeverLeavesZeroAdministrators()
    {
        var adminA = await Factory.SeedMemberAsync(Role.Administrator);
        var adminB = await Factory.SeedMemberAsync(Role.Administrator);

        using var clientA = Factory.CreateClientFor(adminA);
        using var clientB = Factory.CreateClientFor(adminB);
        clientA.DefaultRequestHeaders.Add("If-Match", await Factory.GetMembershipIfMatchAsync(adminB.MembershipId));
        clientB.DefaultRequestHeaders.Add("If-Match", await Factory.GetMembershipIfMatchAsync(adminA.MembershipId));

        var start = new TaskCompletionSource();

        var requestA = RaceDeleteAsync(clientA, adminB, start);
        var requestB = RaceDeleteAsync(clientB, adminA, start);

        start.SetResult();
        var responses = await Task.WhenAll(requestA, requestB);

        responses.Count(r => r.StatusCode == HttpStatusCode.NoContent).Should().BeLessThanOrEqualTo(1);
        responses.Should().OnlyContain(r =>
            r.StatusCode == HttpStatusCode.NoContent || r.StatusCode == HttpStatusCode.Conflict);

        (await CountActiveAdministratorsAsync()).Should().BeGreaterThanOrEqualTo(1);
    }

    private static async Task<HttpResponseMessage> RaceDeleteAsync(
        HttpClient client, SeededMember target, TaskCompletionSource start)
    {
        await start.Task;
        return await client.DeleteAsync($"/members/{target.UserId.Value}", TestContext.Current.CancellationToken);
    }

    private async Task<int> CountActiveAdministratorsAsync()
    {
        using var scope = Factory.Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<IdentityDbContext>();

        return await db.Memberships
            .Where(m => m.Role == Role.Administrator && m.Status == MembershipStatus.Active)
            .CountAsync(TestContext.Current.CancellationToken);
    }
}
