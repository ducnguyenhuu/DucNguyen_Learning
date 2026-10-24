using System.Net;
using System.Net.Http.Json;
using ArchitectureTests.Support;
using AwesomeAssertions;
using Identity.Domain.Abstractions;
using Identity.IntegrationTests.Infrastructure;
using Xunit;

namespace Identity.IntegrationTests.Scenarios;

/// <summary>
/// Acceptance-scenario tests for US2's six acceptance scenarios (spec.md): inviting, accepting,
/// refusing a bad acceptance, removing a member, and protecting the last administrator.
/// </summary>
/// <remarks>
/// Scenarios 3 and 4 overlap <see cref="InvitationRefusalTests"/>' deeper edge-case coverage by
/// design. Scenario 6 is deliberately a simple integration-level acknowledgement: the invariant
/// itself is tested at unit level, and its concurrent variant by
/// <see cref="ConcurrentAdminRemovalTests"/>.
/// </remarks>
public sealed class InviteAndManageMembersTests : IdentityIntegrationTestBase
{
    private const string SeededToken = "some-valid-token-for-seeded-invitee";
    private const string SeededInviteeEmail = "invitee@example.com";

    public InviteAndManageMembersTests(SqlServerFixture sqlServerFixture, ApiFactory factory)
        : base(sqlServerFixture, factory)
    {
    }

    /// <summary>
    /// Scenario 1: an administrator invites an email address with a specified role; an
    /// invitation is recorded as pending with that role and an expiry. Asserted against the
    /// response shape <c>contracts/openapi.yaml</c> documents for <c>POST /invitations</c>: 201
    /// Created, a <c>Location</c> header, and a body containing the invitation's token (returned
    /// once, never stored raw).
    /// </summary>
    [CoversRequirement("FR-011")]
    [Fact]
    public async Task Post_Invitation_WithEmailAndRole_RecordsPendingInvitation()
    {
        var administrator = await Factory.SeedMemberAsync(Role.Administrator);

        using var client = Factory.CreateClientFor(administrator);
        client.DefaultRequestHeaders.Add("Idempotency-Key", Guid.NewGuid().ToString());

        var response = await client.PostAsJsonAsync(
            "/invitations",
            new { email = "new-invitee@example.com", role = "Member" },
            TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.Created);
        response.Headers.Location.Should().NotBeNull();

        var body = await response.Content.ReadAsStringAsync(TestContext.Current.CancellationToken);
        body.Should().Contain("token");
    }

    /// <summary>
    /// Scenario 2: a pending invitation, once accepted by the invited person, makes them an
    /// active member with the invited role. Spans invite, accept, and a subsequent member list
    /// proving the membership exists.
    /// </summary>
    [CoversRequirement("FR-012")]
    [Fact]
    public async Task Post_Invitation_ThenAccept_ThenListMembers_ShowsNewActiveMemberWithInvitedRole()
    {
        var administrator = await Factory.SeedMemberAsync(Role.Administrator);

        using var adminClient = Factory.CreateClientFor(administrator);
        adminClient.DefaultRequestHeaders.Add("Idempotency-Key", Guid.NewGuid().ToString());

        const string invitedEmail = "invited-member@example.com";
        var inviteResponse = await adminClient.PostAsJsonAsync(
            "/invitations",
            new { email = invitedEmail, role = "Member" },
            TestContext.Current.CancellationToken);

        inviteResponse.StatusCode.Should().Be(HttpStatusCode.Created);

        var inviteBody = await inviteResponse.Content.ReadFromJsonAsync<InvitationResponse>(
            TestContext.Current.CancellationToken);
        inviteBody.Should().NotBeNull();
        inviteBody!.Token.Should().NotBeNullOrWhiteSpace();

        using var inviteeClient = Factory.CreateClientForStranger();
        inviteeClient.DefaultRequestHeaders.Add("X-Test-Email", invitedEmail);

        var acceptResponse = await inviteeClient.PostAsync(
            $"/invitations/{inviteBody.Token}/accept",
            content: null,
            TestContext.Current.CancellationToken);

        acceptResponse.StatusCode.Should().Be(HttpStatusCode.OK);

        var membersResponse = await adminClient.GetAsync("/members", TestContext.Current.CancellationToken);

        membersResponse.StatusCode.Should().Be(HttpStatusCode.OK);
        var membersBody = await membersResponse.Content.ReadAsStringAsync(TestContext.Current.CancellationToken);
        membersBody.Should().Contain(invitedEmail);
        membersBody.Should().Contain("Member");
    }

    /// <summary>
    /// The invitation's addressee, authenticated with the matching email and holding the valid
    /// token, can accept it despite having no membership and never having been seen by this API —
    /// which is why the accept route is not member-only. Anchored to a directly persisted
    /// invitation rather than one created over HTTP.
    /// </summary>
    [CoversRequirement("FR-012")]
    [Fact]
    public async Task Post_AcceptInvitation_AsInvitedAddressee_WithNoPriorMembership_Succeeds()
    {
        await Factory.SeedMemberAsync(Role.Administrator);
        await Factory.SeedInvitationAsync(
            SeededInviteeEmail, Role.Member, SeededToken, DateTimeOffset.UtcNow.AddDays(7));

        using var client = Factory.CreateClientForStranger();
        client.DefaultRequestHeaders.Add("X-Test-Email", SeededInviteeEmail);

        var response = await client.PostAsync(
            $"/invitations/{SeededToken}/accept",
            content: null,
            TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.OK);

        var me = await client.GetFromJsonAsync<MeResponse>("/me", TestContext.Current.CancellationToken);
        me!.Role.Should().Be("Member");
    }

    /// <summary>
    /// An invitee who became a member after the invitation was sent (here, an existing member
    /// holding a second invitation) cannot accept it: that would create a second active
    /// membership. The attempt is a 409, not a server error, and the role is unchanged.
    /// </summary>
    [CoversRequirement("FR-012")]
    [Fact]
    public async Task Post_AcceptInvitation_AsExistingMember_IsConflict_AndChangesNothing()
    {
        var member = await Factory.SeedMemberAsync(Role.Administrator, SeededInviteeEmail);
        await Factory.SeedInvitationAsync(
            SeededInviteeEmail, Role.Reader, SeededToken, DateTimeOffset.UtcNow.AddDays(7));

        using var client = Factory.CreateClientFor(member);
        client.DefaultRequestHeaders.Add("X-Test-Email", SeededInviteeEmail);

        var response = await client.PostAsync(
            $"/invitations/{SeededToken}/accept",
            content: null,
            TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.Conflict);

        var me = await client.GetFromJsonAsync<MeResponse>("/me", TestContext.Current.CancellationToken);
        me!.Role.Should().Be("Administrator");
    }

    /// <summary>
    /// Scenario 3: an expired invitation cannot be accepted — the attempt is refused and no
    /// membership is created. Per <c>contracts/openapi.yaml</c>, expired/revoked/already-accepted
    /// tokens are all indistinguishable 404s so token validity can't be probed.
    /// </summary>
    [Fact]
    public async Task Post_AcceptExpiredInvitation_IsRefused()
    {
        await Factory.SeedMemberAsync(Role.Administrator);

        const string invitedEmail = "expired-invitee@example.com";
        const string expiredToken = "some-expired-token";
        await Factory.SeedInvitationAsync(
            invitedEmail, Role.Member, expiredToken, DateTimeOffset.UtcNow.AddDays(-1));

        using var client = Factory.CreateClientForStranger();
        client.DefaultRequestHeaders.Add("X-Test-Email", invitedEmail);

        var response = await client.PostAsync(
            $"/invitations/{expiredToken}/accept",
            content: null,
            TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.NotFound);
    }

    /// <summary>
    /// Scenario 4: an invitation issued to one email address cannot be accepted by a person
    /// authenticated as a different email address. Per <c>contracts/openapi.yaml</c> this is a
    /// distinct 403 (the token is valid, the caller simply isn't its subject) — not a 404. This
    /// requires a genuinely valid, pending invitation token: an unrecognized token always
    /// resolves to 404 first (lookup precedes identity comparison, per FR-013), so the test
    /// creates a real invitation via the invite endpoint and then attempts to accept it while
    /// authenticated as a different email.
    /// </summary>
    [CoversRequirement("FR-013")]
    [Fact]
    public async Task Post_AcceptInvitation_AsDifferentEmailThanInvited_IsRefused()
    {
        var administrator = await Factory.SeedMemberAsync(Role.Administrator);

        using var adminClient = Factory.CreateClientFor(administrator);
        adminClient.DefaultRequestHeaders.Add("Idempotency-Key", Guid.NewGuid().ToString());

        const string invitedEmail = "invited-member@example.com";
        var inviteResponse = await adminClient.PostAsJsonAsync(
            "/invitations",
            new { email = invitedEmail, role = "Member" },
            TestContext.Current.CancellationToken);

        inviteResponse.StatusCode.Should().Be(HttpStatusCode.Created);

        var inviteBody = await inviteResponse.Content.ReadFromJsonAsync<InvitationResponse>(
            TestContext.Current.CancellationToken);
        inviteBody.Should().NotBeNull();
        inviteBody!.Token.Should().NotBeNullOrWhiteSpace();

        using var client = Factory.CreateClientForStranger();
        client.DefaultRequestHeaders.Add("X-Test-Email", "different-person@example.com");

        var response = await client.PostAsync(
            $"/invitations/{inviteBody.Token}/accept",
            content: null,
            TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.Forbidden);
    }

    /// <summary>
    /// FR-013's core rule, with an existing member as the wrong caller: holding a valid,
    /// unexpired token for an invitation issued to someone else's email does not let a different
    /// identity accept it — the token alone is not enough — and the caller's own membership is
    /// left exactly as it was.
    /// </summary>
    [CoversRequirement("FR-013")]
    [Fact]
    public async Task Post_AcceptInvitation_WithValidTokenForSomeoneElse_ByExistingMember_IsRefused()
    {
        var existingMember = await Factory.SeedMemberAsync(Role.Reader);
        await Factory.SeedInvitationAsync(
            SeededInviteeEmail, Role.Administrator, SeededToken, DateTimeOffset.UtcNow.AddDays(7));

        using var client = Factory.CreateClientFor(existingMember);
        client.DefaultRequestHeaders.Add("X-Test-Email", existingMember.Email);

        var response = await client.PostAsync(
            $"/invitations/{SeededToken}/accept",
            content: null,
            TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.Forbidden);

        var me = await client.GetFromJsonAsync<MeResponse>("/me", TestContext.Current.CancellationToken);
        me!.Role.Should().Be("Reader", "a refused acceptance must not upgrade the caller to the invited role");
    }

    /// <summary>
    /// Scenario 5: an administrator removes an active member; that member immediately loses the
    /// ability to read or modify the organization's data. The caller is a genuine Administrator
    /// removing a <em>different</em> person's membership, per spec.md's Scenario 5 wording.
    /// Exercised as remove-then-attempt-read: the removed member is now a non-member, so the
    /// member-only read is refused with 403.
    /// </summary>
    [CoversRequirement("FR-014")]
    [Fact]
    public async Task Delete_ActiveMember_ThenMemberAttemptsToReadOrganizationData_IsRefused()
    {
        var administrator = await Factory.SeedMemberAsync(Role.Administrator);
        var member = await Factory.SeedMemberAsync(Role.Administrator);

        using var adminClient = Factory.CreateClientFor(administrator);
        adminClient.DefaultRequestHeaders.Add("If-Match", await Factory.GetMembershipIfMatchAsync(member.MembershipId));

        var deleteResponse = await adminClient.DeleteAsync(
            $"/members/{member.UserId.Value}",
            TestContext.Current.CancellationToken);

        deleteResponse.StatusCode.Should().Be(HttpStatusCode.NoContent);

        // The target was seeded as an Administrator so the read below would succeed if the
        // removal had not taken effect; after it, the membership filter refuses them.
        using var removedMemberClient = Factory.CreateClientFor(member);

        var readResponse = await removedMemberClient.GetAsync("/members", TestContext.Current.CancellationToken);

        readResponse.StatusCode.Should().Be(HttpStatusCode.Forbidden);
    }

    /// <summary>
    /// Scenario 6: an organization with exactly one administrator refuses an attempt to remove
    /// that administrator, so it cannot become unadministrable.
    /// </summary>
    [CoversRequirement("FR-015")]
    [Fact]
    public async Task Delete_SoleAdministrator_IsRefused()
    {
        var soleAdministrator = await Factory.SeedMemberAsync(Role.Administrator);

        using var client = Factory.CreateClientFor(soleAdministrator);
        client.DefaultRequestHeaders.Add(
            "If-Match", await Factory.GetMembershipIfMatchAsync(soleAdministrator.MembershipId));

        var response = await client.DeleteAsync(
            $"/members/{soleAdministrator.UserId.Value}",
            TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.Conflict);
    }

    private sealed record InvitationResponse(string Token);

    private sealed record MeResponse(Guid UserId, string Email, string? Role);
}
