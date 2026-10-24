using System.Net;
using System.Net.Http.Json;
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
/// <c>POST /members/bootstrap</c> (ADR-025, decision 4): how the organization's first
/// administrator comes to exist. FR-005, as ADR-025 reinterprets it — "the first authenticated
/// user can bootstrap as the first administrator".
/// </summary>
/// <remarks>
/// <para>
/// <b>The rules under test.</b> Bootstrap succeeds only while the organization has no active
/// member at all; after that, people join only by invitation, so a second call is a 409. Only a
/// delegated user token (scope <c>access_as_user</c>) may call it — an application identity
/// must never become the first administrator, so an app-role token is refused with 403 even
/// though it passes the default caller policy everywhere else.
/// </para>
/// <para>
/// <b>Why the concurrent case is an integration test.</b> "Exactly one first administrator" is
/// enforced by <c>MembershipRepository.TryAddFirstAdministratorAsync</c> taking a
/// transaction-scoped <c>sp_getapplock</c> before counting members. That lock only exists in a
/// real SQL Server, so the race can only be proven against one: two genuinely concurrent HTTP
/// requests from different users must yield one 201 and one 409, and the database must hold
/// exactly one active membership afterwards.
/// </para>
/// </remarks>
public sealed class BootstrapAdministratorTests : IdentityIntegrationTestBase
{
    private const string AutomationRole = "Tenancy.Automation.Member";

    public BootstrapAdministratorTests(SqlServerFixture sqlServerFixture, ApiFactory factory)
        : base(sqlServerFixture, factory)
    {
    }

    /// <summary>
    /// The first caller into an empty organization becomes its Administrator: 201 with the
    /// Member body, an <c>ETag</c> for later conditional writes, and a <c>Location</c> naming the
    /// new member. The membership is really persisted, not merely echoed.
    /// </summary>
    [CoversRequirement("FR-005")]
    [Fact]
    public async Task Post_Bootstrap_IntoEmptyOrganization_MakesCallerAdministrator()
    {
        using var client = Factory.CreateClientForStranger();

        var response = await client.PostAsync(
            "/members/bootstrap", content: null, TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.Created);
        response.Headers.ETag.Should().NotBeNull();

        var body = await response.Content.ReadFromJsonAsync<MemberResponse>(TestContext.Current.CancellationToken);
        body.Should().NotBeNull();
        body!.Role.Should().Be("Administrator");
        body.Status.Should().Be("Active");
        response.Headers.Location!.OriginalString.Should().Be($"/members/{body.UserId}");

        var memberships = await GetActiveMembershipsAsync();
        memberships.Should().ContainSingle()
            .Which.Should().Match<Membership>(m => m.UserId == new UserId(body.UserId) && m.Role == Role.Administrator);
    }

    /// <summary>
    /// Once anyone is a member, bootstrap is closed: a second, different user gets 409 and no
    /// membership.
    /// </summary>
    [CoversRequirement("FR-005")]
    [Fact]
    public async Task Post_Bootstrap_WhenOrganizationAlreadyHasAMember_ReturnsConflict()
    {
        await Factory.SeedMemberAsync(Role.Reader);

        using var client = Factory.CreateClientForStranger();

        var response = await client.PostAsync(
            "/members/bootstrap", content: null, TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.Conflict);
        (await GetActiveMembershipsAsync()).Should().ContainSingle()
            .Which.Role.Should().Be(Role.Reader, "the existing member is untouched and nobody was added");
    }

    /// <summary>
    /// The caller who already bootstrapped cannot bootstrap again either — the rule is about the
    /// organization having members, not about who is asking.
    /// </summary>
    [CoversRequirement("FR-005")]
    [Fact]
    public async Task Post_Bootstrap_Twice_BySameCaller_SecondCallReturnsConflict()
    {
        using var client = Factory.CreateClientForStranger();

        var first = await client.PostAsync("/members/bootstrap", content: null, TestContext.Current.CancellationToken);
        var second = await client.PostAsync("/members/bootstrap", content: null, TestContext.Current.CancellationToken);

        first.StatusCode.Should().Be(HttpStatusCode.Created);
        second.StatusCode.Should().Be(HttpStatusCode.Conflict);
        (await GetActiveMembershipsAsync()).Should().ContainSingle();
    }

    /// <summary>
    /// An application identity (app-role token, no delegated scope) is refused with 403 even
    /// into an empty organization — the one case where an otherwise-authorized automation token
    /// is turned away, so a pipeline can never claim the first administrator role.
    /// </summary>
    [CoversRequirement("FR-005")]
    [Fact]
    public async Task Post_Bootstrap_WithApplicationIdentityToken_IsForbidden()
    {
        using var automation = Factory.CreateClientForStranger();
        automation.DefaultRequestHeaders.Add("X-Test-Roles", AutomationRole);

        var response = await automation.PostAsync(
            "/members/bootstrap", content: null, TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.Forbidden);
        (await GetActiveMembershipsAsync()).Should().BeEmpty();
    }

    /// <summary>
    /// Two different users racing to bootstrap an empty organization: exactly one wins (201),
    /// the other is refused (409), and exactly one active membership exists afterwards. Without
    /// the application lock both requests could observe "no members yet" and both insert.
    /// </summary>
    /// <remarks>
    /// The two requests are started together and awaited with <see cref="Task.WhenAll(Task[])"/>
    /// over separate clients, so they reach the server concurrently. A fresh empty organization
    /// is used for several rounds, because a single round can pass by luck if one request happens
    /// to finish before the other starts.
    /// </remarks>
    [CoversRequirement("FR-005")]
    [Fact]
    public async Task Post_Bootstrap_ConcurrentlyByTwoUsers_ExactlyOneBecomesAdministrator()
    {
        const int rounds = 5;

        for (var round = 0; round < rounds; round++)
        {
            await Factory.ResetDatabaseAsync();

            using var first = Factory.CreateClientForStranger();
            using var second = Factory.CreateClientForStranger();

            var responses = await Task.WhenAll(
                first.PostAsync("/members/bootstrap", content: null, TestContext.Current.CancellationToken),
                second.PostAsync("/members/bootstrap", content: null, TestContext.Current.CancellationToken));

            responses.Select(r => r.StatusCode).Should().BeEquivalentTo(
                [HttpStatusCode.Created, HttpStatusCode.Conflict],
                $"round {round}: exactly one concurrent bootstrap may succeed");

            var memberships = await GetActiveMembershipsAsync();
            memberships.Should().ContainSingle($"round {round}: exactly one first administrator may exist")
                .Which.Role.Should().Be(Role.Administrator);
        }
    }

    /// <summary>
    /// A successful bootstrap writes a <c>membership.bootstrapped</c> audit entry naming the new
    /// administrator as both actor and resource; a refused one writes none.
    /// </summary>
    /// <remarks>
    /// <c>AuditEntries</c> is append-only and therefore excluded from the per-test database reset
    /// (see <see cref="ApiFactory.ResetDatabaseAsync"/>), so the assertions are scoped to this
    /// test's own freshly-created users rather than to the table as a whole.
    /// </remarks>
    [CoversRequirement("FR-005")]
    [Fact]
    public async Task Post_Bootstrap_WritesMembershipBootstrappedAuditEntry_OnlyOnSuccess()
    {
        using var winner = Factory.CreateClientForStranger();
        using var loser = Factory.CreateClientForStranger();

        var created = await winner.PostAsync("/members/bootstrap", content: null, TestContext.Current.CancellationToken);
        var refused = await loser.PostAsync("/members/bootstrap", content: null, TestContext.Current.CancellationToken);

        created.StatusCode.Should().Be(HttpStatusCode.Created);
        refused.StatusCode.Should().Be(HttpStatusCode.Conflict);

        var winnerBody = await created.Content.ReadFromJsonAsync<MemberResponse>(TestContext.Current.CancellationToken);
        var winnerId = new UserId(winnerBody!.UserId);

        using var scope = Factory.Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<IdentityDbContext>();

        var bootstrapEntries = await db.AuditEntries
            .AsNoTracking()
            .Where(a => a.Action == "membership.bootstrapped")
            .ToListAsync(TestContext.Current.CancellationToken);

        bootstrapEntries.Where(a => a.ActorUserId == winnerId).Should().ContainSingle()
            .Which.Should().Match<Domain.Auditing.AuditEntry>(a =>
                a.ResourceType == "Membership" && a.ResourceId == winnerId.Value.ToString());

        var loserUserIds = await db.Users
            .AsNoTracking()
            .Where(u => u.Id != winnerId)
            .Select(u => u.Id)
            .ToListAsync(TestContext.Current.CancellationToken);
        loserUserIds.Should().ContainSingle();
        bootstrapEntries.Should().NotContain(a => a.ActorUserId == loserUserIds[0]);
    }

    /// <summary>
    /// Bootstrap requires authentication like every other non-health route: no token, 401, and
    /// nothing written.
    /// </summary>
    [CoversRequirement("FR-002")]
    [Fact]
    public async Task Post_Bootstrap_WithoutAuthentication_IsRejectedAsUnauthenticated()
    {
        using var client = Factory.CreateClient();

        var response = await client.PostAsync(
            "/members/bootstrap", content: null, TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.Unauthorized);
        (await GetActiveMembershipsAsync()).Should().BeEmpty();
    }

    private async Task<List<Membership>> GetActiveMembershipsAsync()
    {
        using var scope = Factory.Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<IdentityDbContext>();
        return await db.Memberships
            .AsNoTracking()
            .Where(m => m.Status == MembershipStatus.Active)
            .ToListAsync(TestContext.Current.CancellationToken);
    }

    private sealed record MemberResponse(Guid UserId, string Email, string Role, string Status);
}
