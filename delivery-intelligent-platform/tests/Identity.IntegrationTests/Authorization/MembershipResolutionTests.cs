using System.Net;
using System.Net.Http.Json;
using ArchitectureTests.Support;
using AwesomeAssertions;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Identity.Domain.Abstractions;
using Identity.Domain.Invitations;
using Identity.Infrastructure.Persistence;
using Identity.IntegrationTests.Infrastructure;
using Xunit;

namespace Identity.IntegrationTests.Authorization;

/// <summary>
/// ADR-025's Compliance promise for <c>MembershipResolutionFilter</c>: every member-only route
/// refuses an authenticated caller who has no active membership with <b>403</b>, and does nothing
/// on their behalf.
/// </summary>
/// <remarks>
/// <para>
/// <b>Why 403 and not 404.</b> With one organization per deployment there is nothing whose
/// existence a non-member could probe, so the refusal says plainly what is wrong: the caller is
/// authenticated but not a member. (Under the retired multi-tenant design the same caller got a
/// 404.) The filter runs before <c>RequireAdministrator()</c>, so a non-member is refused for not
/// being a member, never for lacking a role, and no <c>authorization.refused</c> audit entry is
/// involved.
/// </para>
/// <para>
/// <b>Every route, three kinds of non-member.</b> The theory covers each member-only route
/// (<c>GET /members</c>, <c>PATCH</c>/<c>DELETE /members/{userId}</c>, <c>POST</c>/<c>GET
/// /invitations</c>, <c>DELETE /invitations/{invitationId}</c>) against: an identity this API has
/// never seen; a user who exists (provisioned by <c>GET /me</c>) but was never a member; and a
/// former member whose membership was removed. Each request is otherwise valid — real target
/// ids, a current <c>If-Match</c>, a well-formed body, an <c>Idempotency-Key</c> — so membership
/// is the only thing that can explain the refusal. Afterwards the targets are checked to be
/// unchanged, proving the refusal happened before any write.
/// </para>
/// <para>
/// <c>GET /me</c>, <c>POST /members/bootstrap</c> and <c>POST /invitations/{token}/accept</c> are
/// deliberately not member-only (their caller may not be a member yet) and are covered by
/// <c>MeEndpointTests</c>, <c>BootstrapAdministratorTests</c> and the invitation tests.
/// </para>
/// </remarks>
public sealed class MembershipResolutionTests : IdentityIntegrationTestBase
{
    private const string PendingInviteeEmail = "pending-invitee@example.com";

    public MembershipResolutionTests(SqlServerFixture sqlServerFixture, ApiFactory factory)
        : base(sqlServerFixture, factory)
    {
    }

    /// <summary>Every member-only route, by a stable name the theories report on failure.</summary>
    private static readonly string[] Routes =
    [
        "GET /members",
        "PATCH /members/{userId}",
        "DELETE /members/{userId}",
        "POST /invitations",
        "GET /invitations",
        "DELETE /invitations/{invitationId}",
    ];

    public static TheoryData<string> MemberOnlyRoutes() => new(Routes);

    /// <summary>The kinds of authenticated non-member the theory runs each route against.</summary>
    public enum NonMemberKind
    {
        /// <summary>A token for an identity this API has never seen: no user row at all.</summary>
        NeverSeen,

        /// <summary>A provisioned user who was never a member.</summary>
        ProvisionedButNeverAMember,

        /// <summary>A user whose membership was removed.</summary>
        FormerMember,
    }

    public static TheoryData<string, NonMemberKind> MemberOnlyRoutesByNonMemberKind()
    {
        var data = new TheoryData<string, NonMemberKind>();
        foreach (var route in Routes)
        {
            foreach (var kind in Enum.GetValues<NonMemberKind>())
            {
                data.Add(route, kind);
            }
        }

        return data;
    }

    [CoversRequirement("FR-018")]
    [Theory]
    [MemberData(nameof(MemberOnlyRoutesByNonMemberKind))]
    public async Task MemberOnlyRoute_ByAuthenticatedNonMember_IsForbidden_AndChangesNothing(
        string route, NonMemberKind kind)
    {
        var administrator = await Factory.SeedMemberAsync(Role.Administrator);
        var target = await Factory.SeedMemberAsync(Role.Member);
        var invitationId = await Factory.SeedInvitationAsync(
            PendingInviteeEmail, Role.Member, rawToken: "pending-token", DateTimeOffset.UtcNow.AddDays(7));

        using var nonMember = await CreateNonMemberClientAsync(kind, administrator);

        using var request = await BuildRequestAsync(route, target, invitationId);
        var response = await nonMember.SendAsync(request, TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.Forbidden, $"{route} is member-only and the caller ({kind}) is not a member");

        await AssertNothingChangedAsync(target, invitationId);
    }

    /// <summary>
    /// Reference for the theory above: the same requests from an Administrator are not refused by
    /// membership resolution, so the theory's 403s really are the non-member refusal and not a
    /// route that refuses everybody.
    /// </summary>
    [Theory]
    [MemberData(nameof(MemberOnlyRoutes))]
    public async Task MemberOnlyRoute_ByAdministrator_IsNotForbidden(string route)
    {
        var administrator = await Factory.SeedMemberAsync(Role.Administrator);
        var target = await Factory.SeedMemberAsync(Role.Member);
        var invitationId = await Factory.SeedInvitationAsync(
            PendingInviteeEmail, Role.Member, rawToken: "pending-token", DateTimeOffset.UtcNow.AddDays(7));

        using var client = Factory.CreateClientFor(administrator);

        using var request = await BuildRequestAsync(route, target, invitationId);
        var response = await client.SendAsync(request, TestContext.Current.CancellationToken);

        response.StatusCode.Should().BeOneOf(
            [HttpStatusCode.OK, HttpStatusCode.Created, HttpStatusCode.NoContent],
            $"an Administrator may call {route}");
    }

    /// <summary>
    /// A non-member's 403 says nothing about the organization: whichever route refused it, the
    /// body is identical and carries no member, invitation or caller detail.
    /// </summary>
    [CoversRequirement("FR-022")]
    [Fact]
    public async Task NonMemberRefusal_IsIdenticalAcrossRoutes_AndDisclosesNothing()
    {
        var administrator = await Factory.SeedMemberAsync(Role.Administrator);
        var target = await Factory.SeedMemberAsync(Role.Member);
        var invitationId = await Factory.SeedInvitationAsync(
            PendingInviteeEmail, Role.Member, rawToken: "pending-token", DateTimeOffset.UtcNow.AddDays(7));

        using var nonMember = Factory.CreateClientForStranger();

        var bodies = new List<string>();
        foreach (var route in Routes)
        {
            using var request = await BuildRequestAsync(route, target, invitationId);
            var response = await nonMember.SendAsync(request, TestContext.Current.CancellationToken);
            bodies.Add(await response.Content.ReadAsStringAsync(TestContext.Current.CancellationToken));
        }

        bodies.Distinct().Should().ContainSingle("every member-only route refuses a non-member identically");
        var body = bodies[0];
        body.Should().NotContain(administrator.Email);
        body.Should().NotContain(target.Email);
        body.Should().NotContain(target.UserId.Value.ToString());
        body.Should().NotContain(PendingInviteeEmail);
        body.Should().NotContain(invitationId.Value.ToString());
    }

    private async Task<HttpClient> CreateNonMemberClientAsync(NonMemberKind kind, SeededMember administrator)
    {
        switch (kind)
        {
            case NonMemberKind.NeverSeen:
                return Factory.CreateClientForStranger();

            case NonMemberKind.ProvisionedButNeverAMember:
            {
                var client = Factory.CreateClientForStranger();

                // GET /me JIT-provisions the user without granting any membership.
                var me = await client.GetAsync("/me", TestContext.Current.CancellationToken);
                me.StatusCode.Should().Be(HttpStatusCode.OK);
                return client;
            }

            case NonMemberKind.FormerMember:
            {
                var former = await Factory.SeedMemberAsync(Role.Administrator);

                using var adminClient = Factory.CreateClientFor(administrator);
                adminClient.DefaultRequestHeaders.Add(
                    "If-Match", await Factory.GetMembershipIfMatchAsync(former.MembershipId));
                var removed = await adminClient.DeleteAsync(
                    $"/members/{former.UserId.Value}", TestContext.Current.CancellationToken);
                removed.StatusCode.Should().Be(HttpStatusCode.NoContent);

                return Factory.CreateClientFor(former);
            }

            default:
                throw new ArgumentOutOfRangeException(nameof(kind), kind, null);
        }
    }

    private async Task<HttpRequestMessage> BuildRequestAsync(
        string route, SeededMember target, InvitationId invitationId)
    {
        switch (route)
        {
            case "GET /members":
                return new HttpRequestMessage(HttpMethod.Get, "/members");

            case "PATCH /members/{userId}":
            {
                var request = new HttpRequestMessage(HttpMethod.Patch, $"/members/{target.UserId.Value}")
                {
                    Content = JsonContent.Create(new { role = "Reader" }),
                };
                request.Headers.TryAddWithoutValidation(
                    "If-Match", await Factory.GetMembershipIfMatchAsync(target.MembershipId));
                return request;
            }

            case "DELETE /members/{userId}":
            {
                var request = new HttpRequestMessage(HttpMethod.Delete, $"/members/{target.UserId.Value}");
                request.Headers.TryAddWithoutValidation(
                    "If-Match", await Factory.GetMembershipIfMatchAsync(target.MembershipId));
                return request;
            }

            case "POST /invitations":
            {
                var request = new HttpRequestMessage(HttpMethod.Post, "/invitations")
                {
                    Content = JsonContent.Create(new { email = $"new-{Guid.NewGuid():N}@example.com", role = "Member" }),
                };
                request.Headers.Add("Idempotency-Key", Guid.NewGuid().ToString());
                return request;
            }

            case "GET /invitations":
                return new HttpRequestMessage(HttpMethod.Get, "/invitations");

            case "DELETE /invitations/{invitationId}":
                return new HttpRequestMessage(HttpMethod.Delete, $"/invitations/{invitationId.Value}");

            default:
                throw new ArgumentOutOfRangeException(nameof(route), route, null);
        }
    }

    /// <summary>
    /// The target member still holds their seeded role, the seeded invitation is still pending,
    /// and it is still the only invitation — so no refused request wrote anything.
    /// </summary>
    private async Task AssertNothingChangedAsync(SeededMember target, InvitationId invitationId)
    {
        using var scope = Factory.Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<IdentityDbContext>();

        var membership = await db.Memberships.AsNoTracking()
            .SingleAsync(m => m.Id == target.MembershipId, TestContext.Current.CancellationToken);
        membership.Status.Should().Be(MembershipStatus.Active);
        membership.Role.Should().Be(Role.Member);

        var invitations = await db.Invitations.AsNoTracking().ToListAsync(TestContext.Current.CancellationToken);
        invitations.Should().ContainSingle()
            .Which.Should().Match<Invitation>(i => i.Id == invitationId && i.Status == InvitationStatus.Pending);
    }
}
