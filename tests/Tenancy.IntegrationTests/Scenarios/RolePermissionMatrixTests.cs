using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using AwesomeAssertions;
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
/// T081: the failing permission-matrix test for US3's role-based authorization, covering all four
/// of spec.md's US3 acceptance scenarios against the operation matrix derived from
/// <c>contracts/openapi.yaml</c> and FR-011/014/019.
/// </summary>
/// <remarks>
/// <para>
/// <b>What this file proves right now, and what it doesn't — a different "expected red" shape
/// than T060/T062/T063/T065.</b> Those earlier tests-first files were red because the routes
/// under test were <i>absent</i> from <c>Program.cs</c>'s route table (ASP.NET Core's own
/// "no matching endpoint" 404/405). Every route this file exercises except
/// <c>PATCH /tenants/{tenantId}/members/{userId}</c> (role change — T087's job, see below)
/// already exists and already responds successfully. No role-based authorization exists anywhere
/// in the codebase yet — that's deliberately T085/T088's job, following the exact same
/// "don't add an auth check ahead of the task that owns it" phasing every prior US1/US2 endpoint
/// task used. That means most of this file's non-administrator-refusal assertions
/// (<c>Should().Be(HttpStatusCode.Forbidden)</c>) are red today because the operation currently
/// <b>succeeds</b> (200/201/204) when the eventual, correct behavior is a 403 refusal — not
/// because anything is missing from the route table. This file encodes the eventual-correct
/// behavior per spec.md's User Story 3 so it goes genuinely green, for the right reason, once
/// T085/T088 land.
/// </para>
/// <para>
/// <b>Only two rows, not three (Assumption 5, K3 2026-08-10).</b> Member and Reader have
/// identical effective permissions in this slice — there is no tenant-scoped data to act on until
/// the delivery model arrives (S11), and Story 3's independent test cannot distinguish Member
/// from Reader in S2. Every assertion below is Administrator-vs-non-administrator; no test in
/// this file asserts Member and Reader differ on anything, per the spec's own explicit
/// instruction not to invent an operation solely to make that distinction testable
/// (Principle X). <see cref="Get_TenantDetails_MemberAndReaderBehaveIdentically"/> is the single,
/// explicit parity check the brief allows as "extra confidence" without multiplying the whole
/// matrix by a third row.
/// </para>
/// <para>
/// <b>Scenario 4 (role change) is a target spec, not a working flow.</b>
/// <c>PATCH /tenants/{tenantId}/members/{userId}</c> does not exist as a route at all yet — that's
/// T087's job. <see cref="Patch_MemberRole_AsAdministrator_IsNotYetARoute"/> is therefore the one
/// test in this file that <i>is</i> the earlier route-absent "expected red" shape (404/405 from
/// ASP.NET Core's own routing), consistent with T060/T062/T063's established precedent, kept here
/// as the eventual target for "administrator changes another member's role; that member's
/// permissions change on their next request."
/// </para>
/// <para>
/// <b>No production code changed by this task.</b> Every assertion below documents intended,
/// not-yet-implemented behavior.
/// </para>
/// </remarks>
public sealed class RolePermissionMatrixTests : IClassFixture<ApiFactory>
{
    private readonly ApiFactory _factory;

    public RolePermissionMatrixTests(SqlServerFixture sqlServerFixture, ApiFactory factory)
    {
        _factory = factory;
        _factory.UseConnectionString(sqlServerFixture.ConnectionString);
    }

    /// <summary>
    /// Acceptance scenario 1 (invite): a non-administrator (Member) attempts to invite a new
    /// member and is refused; membership composition is unchanged. Currently red because
    /// <c>POST /tenants/{tenantId}/invitations</c> succeeds (201) for any active member today —
    /// no role check exists yet.
    /// </summary>
    [Fact]
    public async Task Post_Invitation_AsMember_IsRefused()
    {
        await _factory.InitializeDatabaseAsync();
        var seed = await SeedAdministratorAndMemberAsync();

        using var memberClient = CreateAuthenticatedClient(seed.Member);
        memberClient.DefaultRequestHeaders.Add("Idempotency-Key", Guid.NewGuid().ToString());

        var response = await memberClient.PostAsJsonAsync(
            $"/tenants/{seed.Administrator.TenantId.Value}/invitations",
            new { email = "invited-by-member@admin-and-member-tenant.example.com", role = "Member" },
            TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.Forbidden);
    }

    /// <summary>
    /// Acceptance scenario 1 (remove member): a non-administrator (Member) attempts to remove
    /// another active member and is refused; that member's active membership is untouched.
    /// Currently red because <c>DELETE /tenants/{tenantId}/members/{userId}</c> succeeds (204) for
    /// any active member today — no role check exists yet.
    /// </summary>
    [Fact]
    public async Task Delete_Member_AsMember_IsRefused()
    {
        await _factory.InitializeDatabaseAsync();
        var seed = await SeedAdministratorTwoMembersAsync();

        using var memberClient = CreateAuthenticatedClient(seed.Member);
        var ifMatch = await GetMembershipIfMatchAsync(seed.Administrator.TenantId, seed.OtherMember.MembershipId);
        memberClient.DefaultRequestHeaders.Add("If-Match", ifMatch);

        var response = await memberClient.DeleteAsync(
            $"/tenants/{seed.Administrator.TenantId.Value}/members/{seed.OtherMember.UserId.Value}",
            TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.Forbidden);

        using var scope = _factory.Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<TenancyDbContext>();
        db.CurrentTenantId = seed.Administrator.TenantId;
        var membership = await db.Memberships.FindAsync(
            [seed.OtherMember.MembershipId], TestContext.Current.CancellationToken);
        membership.Should().NotBeNull();
        membership!.Status.Should().Be(MembershipStatus.Active);
    }

    /// <summary>
    /// Acceptance scenario 2: a non-administrator (Member) reads tenant details and succeeds —
    /// this one is already green today, and stays green once role checks land, since reads are
    /// not administrator-only.
    /// </summary>
    [Fact]
    public async Task Get_TenantDetails_AsMember_Succeeds()
    {
        await _factory.InitializeDatabaseAsync();
        var seed = await SeedAdministratorAndMemberAsync();

        using var memberClient = CreateAuthenticatedClient(seed.Member);

        var response = await memberClient.GetAsync(
            $"/tenants/{seed.Administrator.TenantId.Value}",
            TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.OK);
    }

    /// <summary>
    /// Single explicit parity check (per the brief's Assumption 5 guidance): Member and Reader
    /// both succeed at reading tenant details, since read access is not administrator-only and
    /// the two roles are, by design, indistinguishable for every operation in this slice. Not a
    /// second matrix row — deliberately the only place this file compares Member and Reader at
    /// all.
    /// </summary>
    [Fact]
    public async Task Get_TenantDetails_MemberAndReaderBehaveIdentically()
    {
        await _factory.InitializeDatabaseAsync();
        var seed = await SeedAdministratorMemberAndReaderAsync();

        using var memberClient = CreateAuthenticatedClient(seed.Member);
        using var readerClient = CreateAuthenticatedClient(seed.Reader);

        var memberResponse = await memberClient.GetAsync(
            $"/tenants/{seed.Administrator.TenantId.Value}",
            TestContext.Current.CancellationToken);
        var readerResponse = await readerClient.GetAsync(
            $"/tenants/{seed.Administrator.TenantId.Value}",
            TestContext.Current.CancellationToken);

        memberResponse.StatusCode.Should().Be(HttpStatusCode.OK);
        readerResponse.StatusCode.Should().Be(memberResponse.StatusCode);
    }

    /// <summary>
    /// Acceptance scenario 3: a Reader attempts to modify tenant settings (rename) and is
    /// refused. Currently red because <c>PATCH /tenants/{tenantId}</c> succeeds (200) for any
    /// active member today — no role check exists yet.
    /// </summary>
    [Fact]
    public async Task Patch_TenantSettings_AsReader_IsRefused()
    {
        await _factory.InitializeDatabaseAsync();
        var seed = await SeedAdministratorAndReaderAsync();

        using var readerClient = CreateAuthenticatedClient(seed.Reader);
        var ifMatch = await GetTenantIfMatchAsync(readerClient, seed.Administrator.TenantId);
        readerClient.DefaultRequestHeaders.Add("If-Match", ifMatch);

        var response = await readerClient.PatchAsJsonAsync(
            $"/tenants/{seed.Administrator.TenantId.Value}",
            new { displayName = "Renamed By Reader" },
            TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.Forbidden);
    }

    /// <summary>
    /// Administrator-side counterpart to the three non-administrator refusals above:
    /// invite/remove/rename all succeed for an Administrator, both today (for the wrong reason —
    /// no check exists) and after T085/T088 land (for the right reason).
    /// </summary>
    [Fact]
    public async Task Post_Invitation_AsAdministrator_Succeeds()
    {
        await _factory.InitializeDatabaseAsync();
        var seed = await SeedAdministratorAndMemberAsync();

        using var adminClient = CreateAuthenticatedClient(seed.Administrator);
        adminClient.DefaultRequestHeaders.Add("Idempotency-Key", Guid.NewGuid().ToString());

        var response = await adminClient.PostAsJsonAsync(
            $"/tenants/{seed.Administrator.TenantId.Value}/invitations",
            new { email = "invited-by-admin@admin-and-member-tenant.example.com", role = "Member" },
            TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.Created);
    }

    /// <summary>
    /// Administrator-only surfaces beyond invite/remove/rename: listing invitations, revoking an
    /// invitation, and listing members are all refused to a non-administrator (Member) per the
    /// matrix — all currently red for the same "succeeds today, no check exists yet" reason.
    /// </summary>
    [Fact]
    public async Task Get_Invitations_AsMember_IsRefused()
    {
        await _factory.InitializeDatabaseAsync();
        var seed = await SeedAdministratorAndMemberAsync();

        using var memberClient = CreateAuthenticatedClient(seed.Member);

        var response = await memberClient.GetAsync(
            $"/tenants/{seed.Administrator.TenantId.Value}/invitations",
            TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.Forbidden);
    }

    /// <summary>
    /// See <see cref="Get_Invitations_AsMember_IsRefused"/>'s remarks — same matrix row, the
    /// revoke-invitation surface.
    /// </summary>
    [Fact]
    public async Task Delete_Invitation_AsMember_IsRefused()
    {
        await _factory.InitializeDatabaseAsync();
        var seed = await SeedAdministratorAndMemberAsync();

        var invitationId = await SeedPendingInvitationAsync(
            seed.Administrator.TenantId, "pending-invitee@admin-and-member-tenant.example.com");

        using var memberClient = CreateAuthenticatedClient(seed.Member);

        var response = await memberClient.DeleteAsync(
            $"/tenants/{seed.Administrator.TenantId.Value}/invitations/{invitationId.Value}",
            TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.Forbidden);
    }

    /// <summary>
    /// See <see cref="Get_Invitations_AsMember_IsRefused"/>'s remarks — same matrix row, the
    /// list-members surface.
    /// </summary>
    [Fact]
    public async Task Get_Members_AsMember_IsRefused()
    {
        await _factory.InitializeDatabaseAsync();
        var seed = await SeedAdministratorAndMemberAsync();

        using var memberClient = CreateAuthenticatedClient(seed.Member);

        var response = await memberClient.GetAsync(
            $"/tenants/{seed.Administrator.TenantId.Value}/members",
            TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.Forbidden);
    }

    /// <summary>
    /// Acceptance scenario 4: an administrator changes another member's role, and that member's
    /// permissions change on their next request. <c>PATCH /tenants/{tenantId}/members/{userId}</c>
    /// does not exist as a route at all yet (T087's job) — this is the earlier, route-absent
    /// "expected red" shape (T060/T062/T063 precedent), not the "succeeds when it should refuse"
    /// shape every other test in this file uses. Written as the target spec: expects the
    /// eventual-correct 200 today, and will fail on ASP.NET Core's own "no matching endpoint"
    /// 404/405 until T087 lands the route.
    /// </summary>
    [Fact]
    public async Task Patch_MemberRole_AsAdministrator_IsNotYetARoute()
    {
        await _factory.InitializeDatabaseAsync();
        var seed = await SeedAdministratorAndMemberAsync();

        using var adminClient = CreateAuthenticatedClient(seed.Administrator);
        var ifMatch = await GetMembershipIfMatchAsync(seed.Administrator.TenantId, seed.Member.MembershipId);
        adminClient.DefaultRequestHeaders.Add("If-Match", ifMatch);

        var response = await adminClient.PatchAsJsonAsync(
            $"/tenants/{seed.Administrator.TenantId.Value}/members/{seed.Member.UserId.Value}",
            new { role = "Administrator" },
            TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.OK);
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
    /// Reads the tenant's current ETag via a genuine <c>GET /tenants/{tenantId}</c> request, so
    /// the PATCH under test presents a valid, non-stale <c>If-Match</c> and actually reaches the
    /// rename logic rather than being short-circuited by the 428/412 precondition checks
    /// <c>TenantEndpoints.PatchTenantAsync</c> (T058) applies before any role check would run.
    /// </summary>
    private static async Task<string> GetTenantIfMatchAsync(HttpClient client, TenantId tenantId)
    {
        var response = await client.GetAsync(
            $"/tenants/{tenantId.Value}", TestContext.Current.CancellationToken);
        response.EnsureSuccessStatusCode();
        return response.Headers.ETag!.ToString();
    }

    /// <summary>
    /// Builds a valid <c>If-Match</c> value directly from the membership's current, persisted
    /// <c>RowVersion</c> — <c>GET /tenants/{tenantId}/members</c> doesn't expose a per-member
    /// ETag, so unlike <see cref="GetTenantIfMatchAsync"/> this reads the row straight from the
    /// database rather than round-tripping through an HTTP response.
    /// </summary>
    private async Task<string> GetMembershipIfMatchAsync(TenantId tenantId, MembershipId membershipId)
    {
        using var scope = _factory.Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<TenancyDbContext>();
        db.CurrentTenantId = tenantId;
        var membership = await db.Memberships.FindAsync(
            [membershipId], TestContext.Current.CancellationToken);
        return RowVersionETag.ToETag(membership!.RowVersion);
    }

    /// <summary>
    /// Seeds a genuinely-persisted, still-pending <see cref="Tenancy.Domain.Invitations.Invitation"/>
    /// in the given tenant — the revoke-invitation refusal test needs a real target id to attempt
    /// revoking, not merely an id that fails to resolve to anything.
    /// </summary>
    private async Task<InvitationId> SeedPendingInvitationAsync(
        TenantId tenantId, string invitedEmail)
    {
        using var scope = _factory.Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<TenancyDbContext>();

        db.CurrentTenantId = tenantId;
        var invitation = Tenancy.Domain.Invitations.Invitation.Create(
            tenantId,
            new EmailAddress(invitedEmail),
            Role.Member,
            tokenHash: $"hash-of-{Guid.NewGuid()}",
            expiresAtUtc: DateTimeOffset.UtcNow.AddDays(7));
        db.Invitations.Add(invitation);
        await db.SaveChangesAsync();

        return invitation.Id;
    }

    /// <summary>
    /// Seeds a single tenant with exactly one active <see cref="Role.Administrator"/> and one
    /// active <see cref="Role.Member"/> — local equivalent of
    /// <see cref="InviteAndManageMembersTests"/>'s (T063) <c>SeedAdministratorAndMemberAsync</c>,
    /// which is <c>private</c> to that class and therefore inaccessible from here, per this task's
    /// brief.
    /// </summary>
    private async Task<AdministratorAndMemberSeed> SeedAdministratorAndMemberAsync()
    {
        using var scope = _factory.Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<TenancyDbContext>();

        var tenant = Tenant.Create("Admin And Member Tenant");
        var admin = User.Create(
            entraTenantId: Guid.CreateVersion7(),
            entraObjectId: Guid.CreateVersion7(),
            email: new EmailAddress("admin@admin-and-member-tenant.example.com"));
        var member = User.Create(
            entraTenantId: Guid.CreateVersion7(),
            entraObjectId: Guid.CreateVersion7(),
            email: new EmailAddress("member@admin-and-member-tenant.example.com"));

        db.Tenants.Add(tenant);
        db.Users.Add(admin);
        db.Users.Add(member);
        await db.SaveChangesAsync();

        db.CurrentTenantId = tenant.Id;
        var adminMembership = Membership.Create(tenant.Id, admin.Id, Role.Administrator);
        var memberMembership = Membership.Create(tenant.Id, member.Id, Role.Member);
        db.Memberships.Add(adminMembership);
        db.Memberships.Add(memberMembership);
        await db.SaveChangesAsync();

        return new AdministratorAndMemberSeed(
            new SeededTenant(tenant.Id, admin.Id, adminMembership.Id, admin.EntraTenantId, admin.EntraObjectId),
            new SeededTenant(tenant.Id, member.Id, memberMembership.Id, member.EntraTenantId, member.EntraObjectId));
    }

    /// <summary>
    /// Same shape as <see cref="SeedAdministratorAndMemberAsync"/> but with <see cref="Role.Reader"/>
    /// instead of <see cref="Role.Member"/> — used only by the rename-refusal test, which
    /// specifically needs a Reader per acceptance scenario 3's wording.
    /// </summary>
    private async Task<AdministratorAndReaderSeed> SeedAdministratorAndReaderAsync()
    {
        using var scope = _factory.Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<TenancyDbContext>();

        var tenant = Tenant.Create("Admin And Reader Tenant");
        var admin = User.Create(
            entraTenantId: Guid.CreateVersion7(),
            entraObjectId: Guid.CreateVersion7(),
            email: new EmailAddress("admin@admin-and-reader-tenant.example.com"));
        var reader = User.Create(
            entraTenantId: Guid.CreateVersion7(),
            entraObjectId: Guid.CreateVersion7(),
            email: new EmailAddress("reader@admin-and-reader-tenant.example.com"));

        db.Tenants.Add(tenant);
        db.Users.Add(admin);
        db.Users.Add(reader);
        await db.SaveChangesAsync();

        db.CurrentTenantId = tenant.Id;
        var adminMembership = Membership.Create(tenant.Id, admin.Id, Role.Administrator);
        var readerMembership = Membership.Create(tenant.Id, reader.Id, Role.Reader);
        db.Memberships.Add(adminMembership);
        db.Memberships.Add(readerMembership);
        await db.SaveChangesAsync();

        return new AdministratorAndReaderSeed(
            new SeededTenant(tenant.Id, admin.Id, adminMembership.Id, admin.EntraTenantId, admin.EntraObjectId),
            new SeededTenant(tenant.Id, reader.Id, readerMembership.Id, reader.EntraTenantId, reader.EntraObjectId));
    }

    /// <summary>
    /// One tenant, one Administrator, one Member, and one Reader — used exclusively by
    /// <see cref="Get_TenantDetails_MemberAndReaderBehaveIdentically"/>, the single explicit parity
    /// check Assumption 5 permits. Not reused elsewhere so no other test in this file is tempted
    /// to grow a third matrix row.
    /// </summary>
    private async Task<AdministratorMemberAndReaderSeed> SeedAdministratorMemberAndReaderAsync()
    {
        using var scope = _factory.Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<TenancyDbContext>();

        var tenant = Tenant.Create("Admin Member Reader Tenant");
        var admin = User.Create(
            entraTenantId: Guid.CreateVersion7(),
            entraObjectId: Guid.CreateVersion7(),
            email: new EmailAddress("admin@admin-member-reader-tenant.example.com"));
        var member = User.Create(
            entraTenantId: Guid.CreateVersion7(),
            entraObjectId: Guid.CreateVersion7(),
            email: new EmailAddress("member@admin-member-reader-tenant.example.com"));
        var reader = User.Create(
            entraTenantId: Guid.CreateVersion7(),
            entraObjectId: Guid.CreateVersion7(),
            email: new EmailAddress("reader@admin-member-reader-tenant.example.com"));

        db.Tenants.Add(tenant);
        db.Users.Add(admin);
        db.Users.Add(member);
        db.Users.Add(reader);
        await db.SaveChangesAsync();

        db.CurrentTenantId = tenant.Id;
        var adminMembership = Membership.Create(tenant.Id, admin.Id, Role.Administrator);
        var memberMembership = Membership.Create(tenant.Id, member.Id, Role.Member);
        var readerMembership = Membership.Create(tenant.Id, reader.Id, Role.Reader);
        db.Memberships.Add(adminMembership);
        db.Memberships.Add(memberMembership);
        db.Memberships.Add(readerMembership);
        await db.SaveChangesAsync();

        return new AdministratorMemberAndReaderSeed(
            new SeededTenant(tenant.Id, admin.Id, adminMembership.Id, admin.EntraTenantId, admin.EntraObjectId),
            new SeededTenant(tenant.Id, member.Id, memberMembership.Id, member.EntraTenantId, member.EntraObjectId),
            new SeededTenant(tenant.Id, reader.Id, readerMembership.Id, reader.EntraTenantId, reader.EntraObjectId));
    }

    /// <summary>
    /// One tenant with an Administrator and two distinct Members — used by
    /// <see cref="Delete_Member_AsMember_IsRefused"/>, which needs a non-administrator caller
    /// attempting to remove a *different* member (not self-removal, and not the sole
    /// administrator, which T067/T068 already own).
    /// </summary>
    private async Task<AdministratorTwoMembersSeed> SeedAdministratorTwoMembersAsync()
    {
        using var scope = _factory.Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<TenancyDbContext>();

        var tenant = Tenant.Create("Admin Two Members Tenant");
        var admin = User.Create(
            entraTenantId: Guid.CreateVersion7(),
            entraObjectId: Guid.CreateVersion7(),
            email: new EmailAddress("admin@admin-two-members-tenant.example.com"));
        var member = User.Create(
            entraTenantId: Guid.CreateVersion7(),
            entraObjectId: Guid.CreateVersion7(),
            email: new EmailAddress("member@admin-two-members-tenant.example.com"));
        var otherMember = User.Create(
            entraTenantId: Guid.CreateVersion7(),
            entraObjectId: Guid.CreateVersion7(),
            email: new EmailAddress("other-member@admin-two-members-tenant.example.com"));

        db.Tenants.Add(tenant);
        db.Users.Add(admin);
        db.Users.Add(member);
        db.Users.Add(otherMember);
        await db.SaveChangesAsync();

        db.CurrentTenantId = tenant.Id;
        var adminMembership = Membership.Create(tenant.Id, admin.Id, Role.Administrator);
        var memberMembership = Membership.Create(tenant.Id, member.Id, Role.Member);
        var otherMemberMembership = Membership.Create(tenant.Id, otherMember.Id, Role.Member);
        db.Memberships.Add(adminMembership);
        db.Memberships.Add(memberMembership);
        db.Memberships.Add(otherMemberMembership);
        await db.SaveChangesAsync();

        return new AdministratorTwoMembersSeed(
            new SeededTenant(tenant.Id, admin.Id, adminMembership.Id, admin.EntraTenantId, admin.EntraObjectId),
            new SeededTenant(tenant.Id, member.Id, memberMembership.Id, member.EntraTenantId, member.EntraObjectId),
            new SeededTenant(
                tenant.Id, otherMember.Id, otherMemberMembership.Id,
                otherMember.EntraTenantId, otherMember.EntraObjectId));
    }

    /// <summary>
    /// A single tenant seeded with two distinct active members: an Administrator (the caller) and
    /// a separate Member (the target). Both <see cref="SeededTenant"/> values share the same
    /// <c>TenantId</c>; only the user/membership/Entra identity fields differ. Local equivalent of
    /// <see cref="InviteAndManageMembersTests"/>'s (T063) private record of the same shape.
    /// </summary>
    private sealed record AdministratorAndMemberSeed(SeededTenant Administrator, SeededTenant Member);

    /// <summary>
    /// Same shape as <see cref="AdministratorAndMemberSeed"/> but with a Reader instead of a
    /// Member.
    /// </summary>
    private sealed record AdministratorAndReaderSeed(SeededTenant Administrator, SeededTenant Reader);

    /// <summary>
    /// One tenant, one Administrator, one Member, and one Reader, all sharing the same
    /// <c>TenantId</c>.
    /// </summary>
    private sealed record AdministratorMemberAndReaderSeed(
        SeededTenant Administrator, SeededTenant Member, SeededTenant Reader);

    /// <summary>
    /// One tenant, one Administrator, and two distinct Members, all sharing the same
    /// <c>TenantId</c>.
    /// </summary>
    private sealed record AdministratorTwoMembersSeed(
        SeededTenant Administrator, SeededTenant Member, SeededTenant OtherMember);
}
