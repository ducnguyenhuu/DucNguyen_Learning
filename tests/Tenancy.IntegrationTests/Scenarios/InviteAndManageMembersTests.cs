using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using AwesomeAssertions;
using Microsoft.Extensions.DependencyInjection;
using Tenancy.Domain.Abstractions;
using Tenancy.Domain.Invitations;
using Tenancy.Domain.Memberships;
using Tenancy.Domain.Tenants;
using Tenancy.Domain.Users;
using Tenancy.Infrastructure.Persistence;
using Tenancy.IntegrationTests.Infrastructure;
using Xunit;

namespace Tenancy.IntegrationTests.Scenarios;

/// <summary>
/// Failing acceptance-scenario tests (T063) for US2's six acceptance scenarios (spec.md).
/// </summary>
/// <remarks>
/// <b>What this file proves right now, and what it doesn't.</b> Same caveat as
/// <see cref="EstablishTenantTests"/> (T045) and
/// <see cref="Isolation.MembershipEndpointIsolationTests"/> (T062): none of the invitation/member
/// endpoints exist yet (T070-T080 add them), so every request below hits a route absent from
/// <c>Program.cs</c>'s route table and gets ASP.NET Core's own "no matching endpoint" 404/405 —
/// not any real business rule. These tests encode the eventual-correct behavior per spec.md's
/// User Story 2 so they go genuinely green once the endpoints land. Scenarios 3 and 4 overlap
/// T064/T065's deeper edge-case coverage by design (see task-63-brief.md's scope note); scenario 6
/// is deliberately kept to a simple integration-level acknowledgement, with the real invariant
/// tested at unit level by T067 and its concurrent variant by T068.
/// </remarks>
public sealed class InviteAndManageMembersTests : IClassFixture<ApiFactory>
{
    private readonly ApiFactory _factory;

    public InviteAndManageMembersTests(SqlServerFixture sqlServerFixture, ApiFactory factory)
    {
        _factory = factory;
        _factory.UseConnectionString(sqlServerFixture.ConnectionString);
    }

    /// <summary>
    /// Scenario 1: an authenticated tenant administrator invites an email address with a
    /// specified role; an invitation is recorded as pending against that tenant with that role
    /// and an expiry. Asserted against the response shape <c>contracts/openapi.yaml</c> documents
    /// for <c>POST /tenants/{tenantId}/invitations</c>: 201 Created, a <c>Location</c> header, and
    /// a body containing the invitation's token (returned once, never stored raw).
    /// </summary>
    [Fact]
    public async Task Post_Invitation_WithEmailAndRole_RecordsPendingInvitation()
    {
        await _factory.InitializeDatabaseAsync();
        var seed = await _factory.SeedTwoTenantsAsync();

        using var client = CreateAuthenticatedClient(seed.TenantA);
        client.DefaultRequestHeaders.Add("Idempotency-Key", Guid.NewGuid().ToString());

        var response = await client.PostAsJsonAsync(
            $"/tenants/{seed.TenantA.TenantId.Value}/invitations",
            new { email = "new-invitee@tenant-a.example.com", role = "Member" },
            TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.Created);
        response.Headers.Location.Should().NotBeNull();

        var body = await response.Content.ReadAsStringAsync(TestContext.Current.CancellationToken);
        body.Should().Contain("token");
    }

    /// <summary>
    /// Scenario 2: a pending invitation, once accepted by the invited person, makes them an
    /// active member with the invited role, and the invitation is marked accepted and cannot be
    /// reused. This spans invite + accept + a subsequent read proving membership — since none of
    /// this exists yet, it's expected to fail at the invite step rather than exercise the full
    /// flow; that's the accepted state for this tests-first sub-phase (see task-63-brief.md).
    /// </summary>
    [Fact]
    public async Task Post_Invitation_ThenAccept_ThenListMembers_ShowsNewActiveMemberWithInvitedRole()
    {
        await _factory.InitializeDatabaseAsync();
        var seed = await _factory.SeedTwoTenantsAsync();

        using var adminClient = CreateAuthenticatedClient(seed.TenantA);
        adminClient.DefaultRequestHeaders.Add("Idempotency-Key", Guid.NewGuid().ToString());

        const string invitedEmail = "invited-member@tenant-a.example.com";
        var inviteResponse = await adminClient.PostAsJsonAsync(
            $"/tenants/{seed.TenantA.TenantId.Value}/invitations",
            new { email = invitedEmail, role = "Member" },
            TestContext.Current.CancellationToken);

        inviteResponse.StatusCode.Should().Be(HttpStatusCode.Created);

        var inviteBody = await inviteResponse.Content.ReadFromJsonAsync<InvitationResponse>(
            TestContext.Current.CancellationToken);
        inviteBody.Should().NotBeNull();
        inviteBody!.Token.Should().NotBeNullOrWhiteSpace();

        using var inviteeClient = _factory.CreateClient();
        inviteeClient.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("TestScheme", "test");
        inviteeClient.DefaultRequestHeaders.Add("X-Test-Oid", Guid.NewGuid().ToString());
        inviteeClient.DefaultRequestHeaders.Add("X-Test-Tid", Guid.NewGuid().ToString());
        inviteeClient.DefaultRequestHeaders.Add("X-Test-Email", invitedEmail);

        var acceptResponse = await inviteeClient.PostAsync(
            $"/invitations/{inviteBody.Token}/accept",
            content: null,
            TestContext.Current.CancellationToken);

        acceptResponse.StatusCode.Should().Be(HttpStatusCode.OK);

        var membersResponse = await adminClient.GetAsync(
            $"/tenants/{seed.TenantA.TenantId.Value}/members",
            TestContext.Current.CancellationToken);

        membersResponse.StatusCode.Should().Be(HttpStatusCode.OK);
        var membersBody = await membersResponse.Content.ReadAsStringAsync(TestContext.Current.CancellationToken);
        membersBody.Should().Contain(invitedEmail);
        membersBody.Should().Contain("Member");
    }

    /// <summary>
    /// Scenario 3: an expired invitation cannot be accepted — the attempt is refused and no
    /// membership is created. Per <c>contracts/openapi.yaml</c>, expired/revoked/already-accepted
    /// tokens are all indistinguishable 404s so token validity can't be probed.
    /// </summary>
    [Fact]
    public async Task Post_AcceptExpiredInvitation_IsRefused()
    {
        await _factory.InitializeDatabaseAsync();
        var seed = await _factory.SeedTwoTenantsAsync();

        const string invitedEmail = "expired-invitee@tenant-a.example.com";
        await SeedExpiredInvitationAsync(seed.TenantA.TenantId, invitedEmail);

        using var client = _factory.CreateClient();
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("TestScheme", "test");
        client.DefaultRequestHeaders.Add("X-Test-Oid", Guid.NewGuid().ToString());
        client.DefaultRequestHeaders.Add("X-Test-Tid", Guid.NewGuid().ToString());
        client.DefaultRequestHeaders.Add("X-Test-Email", invitedEmail);

        var response = await client.PostAsync(
            "/invitations/some-expired-token/accept",
            content: null,
            TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.NotFound);
    }

    /// <summary>
    /// Scenario 4: an invitation issued to one email address cannot be accepted by a person
    /// authenticated as a different email address. Per <c>contracts/openapi.yaml</c> this is a
    /// distinct 403 (the token is valid, the caller simply isn't its subject) — not a 404.
    /// </summary>
    [Fact]
    public async Task Post_AcceptInvitation_AsDifferentEmailThanInvited_IsRefused()
    {
        await _factory.InitializeDatabaseAsync();
        var seed = await _factory.SeedTwoTenantsWithInvitationInTenantBAsync();

        // The invitation seeded by SeedTwoTenantsWithInvitationInTenantBAsync targets
        // invitee@tenant-b.example.com; here the caller authenticates as a different identity
        // entirely (Tenant A's member) and attempts to accept it anyway.
        using var client = _factory.CreateClient();
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("TestScheme", "test");
        client.DefaultRequestHeaders.Add("X-Test-Oid", seed.TenantA.EntraObjectId.ToString());
        client.DefaultRequestHeaders.Add("X-Test-Tid", seed.TenantA.EntraTenantId.ToString());
        client.DefaultRequestHeaders.Add("X-Test-Email", "member-a@tenant-a.example.com");

        var response = await client.PostAsync(
            "/invitations/some-opaque-token/accept",
            content: null,
            TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.Forbidden);
    }

    /// <summary>
    /// Scenario 5: an authenticated tenant administrator removes an active member; that member
    /// immediately loses the ability to read or modify any of the tenant's data. Exercised as
    /// remove-then-attempt-read, both against the same tenant.
    /// </summary>
    [Fact]
    public async Task Delete_ActiveMember_ThenMemberAttemptsToReadTenantData_IsRefused()
    {
        await _factory.InitializeDatabaseAsync();
        var seed = await _factory.SeedTwoTenantsAsync();

        using var adminClient = CreateAuthenticatedClient(seed.TenantA);

        var deleteResponse = await adminClient.DeleteAsync(
            $"/tenants/{seed.TenantA.TenantId.Value}/members/{seed.TenantA.UserId.Value}",
            TestContext.Current.CancellationToken);

        deleteResponse.StatusCode.Should().Be(HttpStatusCode.NoContent);

        using var removedMemberClient = CreateAuthenticatedClient(seed.TenantA);

        var readResponse = await removedMemberClient.GetAsync(
            $"/tenants/{seed.TenantA.TenantId.Value}",
            TestContext.Current.CancellationToken);

        readResponse.StatusCode.Should().NotBe(HttpStatusCode.OK);
    }

    /// <summary>
    /// Scenario 6: a tenant with exactly one administrator refuses an attempt to remove that
    /// administrator, so the tenant cannot become unadministrable. Kept to a simple
    /// integration-level acknowledgement per task-63-brief.md's scope note — the deep unit-level
    /// invariant is T067's job, and the concurrent-race variant is T068's.
    /// </summary>
    [Fact]
    public async Task Delete_SoleAdministrator_IsRefused()
    {
        await _factory.InitializeDatabaseAsync();
        var seed = await SeedSoleAdministratorTenantAsync();

        using var client = _factory.CreateClient();
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("TestScheme", "test");
        client.DefaultRequestHeaders.Add("X-Test-Oid", seed.EntraObjectId.ToString());
        client.DefaultRequestHeaders.Add("X-Test-Tid", seed.EntraTenantId.ToString());

        var response = await client.DeleteAsync(
            $"/tenants/{seed.TenantId.Value}/members/{seed.UserId.Value}",
            TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.Conflict);
    }

    private HttpClient CreateAuthenticatedClient(SeededTenant seededTenant)
    {
        var client = _factory.CreateClient();
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("TestScheme", "test");
        client.DefaultRequestHeaders.Add("X-Test-Oid", seededTenant.EntraObjectId.ToString());
        client.DefaultRequestHeaders.Add("X-Test-Tid", seededTenant.EntraTenantId.ToString());
        return client;
    }

    /// <summary>
    /// Seeds a genuinely-persisted, already-expired <see cref="Invitation"/> in the given tenant —
    /// scenario 3 needs the accept attempt to target an invitation that legitimately exists (and
    /// is legitimately expired), not merely a token that fails to resolve to anything.
    /// </summary>
    private async Task SeedExpiredInvitationAsync(TenantId tenantId, string invitedEmail)
    {
        using var scope = _factory.Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<TenancyDbContext>();

        db.CurrentTenantId = tenantId;
        var invitation = Invitation.Create(
            tenantId,
            new EmailAddress(invitedEmail),
            Role.Member,
            tokenHash: "expired-token-hash",
            expiresAtUtc: DateTimeOffset.UtcNow.AddDays(-1));
        db.Invitations.Add(invitation);
        await db.SaveChangesAsync();
    }

    /// <summary>
    /// Seeds a single tenant with exactly one active <see cref="Role.Administrator"/> member —
    /// the fixture scenario 6 needs to attempt removing the last administrator.
    /// </summary>
    private async Task<SeededTenant> SeedSoleAdministratorTenantAsync()
    {
        using var scope = _factory.Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<TenancyDbContext>();

        var tenant = Tenant.Create("Sole Admin Tenant");
        var admin = User.Create(
            entraTenantId: Guid.CreateVersion7(),
            entraObjectId: Guid.CreateVersion7(),
            email: new EmailAddress("sole-admin@sole-admin-tenant.example.com"));

        db.Tenants.Add(tenant);
        db.Users.Add(admin);
        await db.SaveChangesAsync();

        db.CurrentTenantId = tenant.Id;
        var membership = Membership.Create(tenant.Id, admin.Id, Role.Administrator);
        db.Memberships.Add(membership);
        await db.SaveChangesAsync();

        return new SeededTenant(tenant.Id, admin.Id, membership.Id, admin.EntraTenantId, admin.EntraObjectId);
    }

    private sealed record InvitationResponse(string Token);
}
