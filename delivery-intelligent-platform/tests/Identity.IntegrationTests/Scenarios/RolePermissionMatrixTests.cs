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

namespace Identity.IntegrationTests.Scenarios;

/// <summary>
/// The permission matrix for US3's role-based authorization: every administrator-only route
/// refuses a Member and a Reader with 403, succeeds for an Administrator, and a role change takes
/// effect on the changed member's next request. ADR-025's Compliance section names this file as
/// the proof that every administrator-only route refuses Member and Reader.
/// </summary>
/// <remarks>
/// <para>
/// <b>The routes.</b> All of <c>/members</c> and <c>/invitations</c> except accept are
/// administrator-only: <c>GET /members</c>, <c>PATCH</c>/<c>DELETE /members/{userId}</c>,
/// <c>POST</c>/<c>GET /invitations</c> and <c>DELETE /invitations/{invitationId}</c> (FR-011,
/// FR-014, FR-019). The refusal comes from <c>RequireAdministrator()</c>, which reads the role
/// that <c>MembershipResolutionFilter</c> resolved from the database, never a token claim — so
/// these callers are genuine, active members who simply lack the role. (A caller who is not a
/// member at all is refused one step earlier; see <c>MembershipResolutionTests</c>.)
/// </para>
/// <para>
/// <b>What each refusal must prove.</b> 403 rather than 401 (forbidden, distinctly from
/// unauthenticated — FR-018); nothing written by the refused request; and an
/// <c>authorization.refused</c> audit entry naming the refused caller (FR-025's "authorisation
/// refusal" is the logging half; the audit row is the durable half).
/// </para>
/// <para>
/// <b>Member and Reader are the same row (Assumption 5, K3 2026-08-10).</b> They have identical
/// effective permissions in this slice — there is no delivery data to act on until S11 — so the
/// matrix runs both through the same theory rather than inventing an operation that tells them
/// apart (Principle X).
/// </para>
/// </remarks>
public sealed class RolePermissionMatrixTests : IdentityIntegrationTestBase
{
    private const string PendingInviteeEmail = "pending-invitee@example.com";

    private static readonly string[] AdministratorOnlyRoutes =
    [
        "GET /members",
        "PATCH /members/{userId}",
        "DELETE /members/{userId}",
        "POST /invitations",
        "GET /invitations",
        "DELETE /invitations/{invitationId}",
    ];

    public RolePermissionMatrixTests(SqlServerFixture sqlServerFixture, ApiFactory factory)
        : base(sqlServerFixture, factory)
    {
    }

    public static TheoryData<string, Role> AdministratorOnlyRoutesByNonAdministratorRole()
    {
        var data = new TheoryData<string, Role>();
        foreach (var route in AdministratorOnlyRoutes)
        {
            data.Add(route, Role.Member);
            data.Add(route, Role.Reader);
        }

        return data;
    }

    public static TheoryData<string> AdministratorOnlyRouteNames() => new(AdministratorOnlyRoutes);

    /// <summary>
    /// US3 acceptance scenarios 1 and 3: a Member or Reader attempting any administrator-only
    /// operation is refused with 403, nothing changes, and the refusal is audited.
    /// </summary>
    [CoversRequirement("FR-018")]
    [CoversRequirement("FR-019")]
    [Theory]
    [MemberData(nameof(AdministratorOnlyRoutesByNonAdministratorRole))]
    public async Task AdministratorOnlyRoute_AsNonAdministrator_IsForbidden_ChangesNothing_AndIsAudited(
        string route, Role callerRole)
    {
        var seed = await SeedAsync();
        var caller = await Factory.SeedMemberAsync(callerRole);

        using var client = Factory.CreateClientFor(caller);
        using var request = await BuildRequestAsync(route, seed);

        var response = await client.SendAsync(request, TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.Forbidden, $"{route} is administrator-only and the caller is a {callerRole}");

        using var scope = Factory.Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<IdentityDbContext>();

        var target = await db.Memberships.AsNoTracking()
            .SingleAsync(m => m.Id == seed.Target.MembershipId, TestContext.Current.CancellationToken);
        target.Status.Should().Be(MembershipStatus.Active);
        target.Role.Should().Be(Role.Member);

        var invitations = await db.Invitations.AsNoTracking().ToListAsync(TestContext.Current.CancellationToken);
        invitations.Should().ContainSingle()
            .Which.Should().Match<Invitation>(i => i.Id == seed.InvitationId && i.Status == InvitationStatus.Pending);

        // AuditEntries is not reset between tests (append-only), so scope to this caller.
        var refusals = await db.AuditEntries.AsNoTracking()
            .Where(a => a.ActorUserId == caller.UserId && a.Action == "authorization.refused")
            .ToListAsync(TestContext.Current.CancellationToken);
        refusals.Should().ContainSingle();
    }

    /// <summary>
    /// The Administrator-side counterpart: the identical, otherwise-valid requests all succeed for
    /// an Administrator, so the refusals above are about role and nothing else.
    /// </summary>
    [CoversRequirement("FR-011")]
    [CoversRequirement("FR-019")]
    [Theory]
    [MemberData(nameof(AdministratorOnlyRouteNames))]
    public async Task AdministratorOnlyRoute_AsAdministrator_Succeeds(string route)
    {
        var seed = await SeedAsync();

        using var client = Factory.CreateClientFor(seed.Administrator);
        using var request = await BuildRequestAsync(route, seed);

        var response = await client.SendAsync(request, TestContext.Current.CancellationToken);

        response.StatusCode.Should().BeOneOf(
            [HttpStatusCode.OK, HttpStatusCode.Created, HttpStatusCode.NoContent],
            $"an Administrator may call {route}");
    }

    /// <summary>
    /// A role refusal is generic: the 403 body for one wrong-role caller is byte-for-byte the
    /// 403 body for a different wrong-role caller, and names no caller, member or invitation.
    /// Any divergence would mean the "generic" refusal leaks caller-specific detail.
    /// </summary>
    [CoversRequirement("FR-018")]
    [Fact]
    public async Task RoleRefusal_IsGeneric_AndIdenticalAcrossCallers()
    {
        var seed = await SeedAsync();
        var member = await Factory.SeedMemberAsync(Role.Member);
        var reader = await Factory.SeedMemberAsync(Role.Reader);

        using var memberClient = Factory.CreateClientFor(member);
        using var readerClient = Factory.CreateClientFor(reader);
        using var memberRequest = await BuildRequestAsync("POST /invitations", seed);
        using var readerRequest = await BuildRequestAsync("POST /invitations", seed);

        var memberResponse = await memberClient.SendAsync(memberRequest, TestContext.Current.CancellationToken);
        var readerResponse = await readerClient.SendAsync(readerRequest, TestContext.Current.CancellationToken);

        memberResponse.StatusCode.Should().Be(HttpStatusCode.Forbidden);
        readerResponse.StatusCode.Should().Be(HttpStatusCode.Forbidden);

        var memberBody = await memberResponse.Content.ReadAsStringAsync(TestContext.Current.CancellationToken);
        var readerBody = await readerResponse.Content.ReadAsStringAsync(TestContext.Current.CancellationToken);

        memberBody.Should().Be(readerBody);
        memberBody.Should().NotContain(member.Email);
        memberBody.Should().NotContain(seed.Administrator.Email);
        memberBody.Should().NotContain(PendingInviteeEmail);
    }

    /// <summary>
    /// US3 acceptance scenario 2 and the Member/Reader parity check: the one read every member
    /// may make, <c>GET /me</c>, succeeds for both and differs only in the role it reports.
    /// </summary>
    [Fact]
    public async Task Get_Me_MemberAndReaderBehaveIdentically()
    {
        var member = await Factory.SeedMemberAsync(Role.Member);
        var reader = await Factory.SeedMemberAsync(Role.Reader);

        using var memberClient = Factory.CreateClientFor(member);
        using var readerClient = Factory.CreateClientFor(reader);

        var memberResponse = await memberClient.GetAsync("/me", TestContext.Current.CancellationToken);
        var readerResponse = await readerClient.GetAsync("/me", TestContext.Current.CancellationToken);

        memberResponse.StatusCode.Should().Be(HttpStatusCode.OK);
        readerResponse.StatusCode.Should().Be(memberResponse.StatusCode);
    }

    /// <summary>
    /// US3 acceptance scenario 4: an administrator changes another member's role, and that
    /// member's permissions change on their very next request — no re-sign-in, because the role
    /// is resolved from the database per request, not read from the token.
    /// </summary>
    [CoversRequirement("FR-014")]
    [CoversRequirement("FR-019")]
    [Fact]
    public async Task Patch_MemberRole_ToAdministrator_TakesEffectOnTheMembersNextRequest()
    {
        var administrator = await Factory.SeedMemberAsync(Role.Administrator);
        var member = await Factory.SeedMemberAsync(Role.Member);

        using var memberClient = Factory.CreateClientFor(member);
        var before = await memberClient.GetAsync("/members", TestContext.Current.CancellationToken);
        before.StatusCode.Should().Be(HttpStatusCode.Forbidden);

        using var adminClient = Factory.CreateClientFor(administrator);
        adminClient.DefaultRequestHeaders.Add("If-Match", await Factory.GetMembershipIfMatchAsync(member.MembershipId));

        var patch = await adminClient.PatchAsJsonAsync(
            $"/members/{member.UserId.Value}",
            new { role = "Administrator" },
            TestContext.Current.CancellationToken);
        patch.StatusCode.Should().Be(HttpStatusCode.OK);

        var after = await memberClient.GetAsync("/members", TestContext.Current.CancellationToken);
        after.StatusCode.Should().Be(HttpStatusCode.OK);
    }

    /// <summary>
    /// The shared cast for the matrix: an Administrator, a Member who is the target of the
    /// member-scoped routes, and a pending invitation that is the target of the revoke route.
    /// The calling non-administrator is seeded separately by each test.
    /// </summary>
    private async Task<MatrixSeed> SeedAsync()
    {
        var administrator = await Factory.SeedMemberAsync(Role.Administrator);
        var target = await Factory.SeedMemberAsync(Role.Member);
        var invitationId = await Factory.SeedInvitationAsync(
            PendingInviteeEmail, Role.Member, rawToken: $"token-{Guid.NewGuid():N}", DateTimeOffset.UtcNow.AddDays(7));

        return new MatrixSeed(administrator, target, invitationId);
    }

    /// <summary>
    /// A fully valid request for <paramref name="route"/> — a real target, a current
    /// <c>If-Match</c>, a well-formed body, an <c>Idempotency-Key</c> — so that role is the only
    /// thing that can explain a refusal.
    /// </summary>
    private async Task<HttpRequestMessage> BuildRequestAsync(string route, MatrixSeed seed)
    {
        switch (route)
        {
            case "GET /members":
                return new HttpRequestMessage(HttpMethod.Get, "/members");

            case "PATCH /members/{userId}":
            {
                var request = new HttpRequestMessage(HttpMethod.Patch, $"/members/{seed.Target.UserId.Value}")
                {
                    Content = JsonContent.Create(new { role = "Reader" }),
                };
                request.Headers.TryAddWithoutValidation(
                    "If-Match", await Factory.GetMembershipIfMatchAsync(seed.Target.MembershipId));
                return request;
            }

            case "DELETE /members/{userId}":
            {
                var request = new HttpRequestMessage(HttpMethod.Delete, $"/members/{seed.Target.UserId.Value}");
                request.Headers.TryAddWithoutValidation(
                    "If-Match", await Factory.GetMembershipIfMatchAsync(seed.Target.MembershipId));
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
                return new HttpRequestMessage(HttpMethod.Delete, $"/invitations/{seed.InvitationId.Value}");

            default:
                throw new ArgumentOutOfRangeException(nameof(route), route, null);
        }
    }

    private sealed record MatrixSeed(SeededMember Administrator, SeededMember Target, InvitationId InvitationId);
}
