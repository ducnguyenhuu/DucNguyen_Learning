using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using ArchitectureTests.Support;
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
/// Failing tests (T083) for <c>PATCH /tenants/{tenantId}/members/{userId}</c> — changing an
/// active member's role, including refusal when the change would demote the tenant's sole
/// remaining <see cref="Role.Administrator"/> (T074's <see cref="TenantAdministration"/>
/// invariant, exercised here end-to-end once T086/T087 land).
/// </summary>
/// <remarks>
/// <b>What this file proves right now, and what it doesn't.</b> Same caveat as
/// <see cref="InviteAndManageMembersTests"/> (T063) and
/// <see cref="RolePermissionMatrixTests"/>'s <c>Patch_MemberRole_AsAdministrator_IsNotYetARoute</c>
/// (T082): <c>PATCH /tenants/{tenantId}/members/{userId}</c> does not exist as a route at all yet
/// (T087's job), so every request below hits ASP.NET Core's own "no matching endpoint" 404/405
/// rather than any real business rule. These tests encode the eventual-correct behavior per
/// <c>contracts/openapi.yaml</c> so they go genuinely green once T086/T087 land.
/// </remarks>
public sealed class ChangeMemberRoleTests : TenancyIntegrationTestBase
{

    public ChangeMemberRoleTests(SqlServerFixture sqlServerFixture, ApiFactory factory)
        : base(sqlServerFixture, factory)
    {
    }

    /// <summary>
    /// Happy path: an administrator changes another member's role from <see cref="Role.Member"/>
    /// to <see cref="Role.Reader"/> — per Assumption 5, Member and Reader are behaviorally
    /// identical, so this is purely a mechanism check, not a proof of behavioral difference.
    /// Asserts <c>200</c>, the new role in the response body, and a fresh <c>ETag</c> distinct
    /// from the <c>If-Match</c> presented on the request.
    /// </summary>
    [CoversRequirement("FR-014")]
    [Fact]
    public async Task Patch_MemberRole_AsAdministrator_ChangesRoleAndReturnsFreshETag()
    {
        await Factory.InitializeDatabaseAsync();
        var seed = await SeedAdministratorAndMemberAsync();

        using var adminClient = CreateAuthenticatedClient(seed.Administrator);
        var ifMatch = await GetMembershipIfMatchAsync(seed.Administrator.TenantId, seed.Member.MembershipId);
        adminClient.DefaultRequestHeaders.Add("If-Match", ifMatch);

        var response = await adminClient.PatchAsJsonAsync(
            $"/tenants/{seed.Administrator.TenantId.Value}/members/{seed.Member.UserId.Value}",
            new { role = "Reader" },
            TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.OK);

        var body = await response.Content.ReadAsStringAsync(TestContext.Current.CancellationToken);
        body.Should().Contain("Reader");

        response.Headers.ETag.Should().NotBeNull();
        response.Headers.ETag!.ToString().Should().NotBe(ifMatch);
    }

    /// <summary>
    /// Last-administrator demotion refusal: a tenant's sole administrator attempts to change
    /// their own role away from <see cref="Role.Administrator"/>. Per T074's
    /// <see cref="TenantAdministration.EnsureRoleChangeAllowed"/>, this must be refused with
    /// <c>409 Conflict</c> rather than leaving the tenant with zero active administrators.
    /// </summary>
    [CoversRequirement("FR-015")]
    [Fact]
    public async Task Patch_MemberRole_SoleAdministratorDemotesSelf_IsRefused()
    {
        await Factory.InitializeDatabaseAsync();
        var seed = await SeedSoleAdministratorTenantAsync();

        using var client = Factory.CreateClient();
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("TestScheme", "test");
        client.DefaultRequestHeaders.Add("X-Test-Oid", seed.EntraObjectId.ToString());
        client.DefaultRequestHeaders.Add("X-Test-Tid", seed.EntraTenantId.ToString());

        var ifMatch = await GetMembershipIfMatchAsync(seed.TenantId, seed.MembershipId);
        client.DefaultRequestHeaders.Add("If-Match", ifMatch);

        var response = await client.PatchAsJsonAsync(
            $"/tenants/{seed.TenantId.Value}/members/{seed.UserId.Value}",
            new { role = "Member" },
            TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.Conflict);
    }

    /// <summary>
    /// <c>If-Match</c> handling, test 1: a request with no <c>If-Match</c> header at all is
    /// rejected with <c>428 Precondition Required</c>, mirroring T058's PATCH tenant and T079's
    /// DELETE member precedent.
    /// </summary>
    [CoversRequirement("FR-014")]
    [CoversRequirement("FR-021")]
    [Fact]
    public async Task Patch_MemberRole_WithoutIfMatchHeader_ReturnsPreconditionRequired()
    {
        await Factory.InitializeDatabaseAsync();
        var seed = await SeedAdministratorAndMemberAsync();

        using var adminClient = CreateAuthenticatedClient(seed.Administrator);

        var response = await adminClient.PatchAsJsonAsync(
            $"/tenants/{seed.Administrator.TenantId.Value}/members/{seed.Member.UserId.Value}",
            new { role = "Reader" },
            TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be((HttpStatusCode)428);
    }

    /// <summary>
    /// <c>If-Match</c> handling, test 2: a malformed <c>If-Match</c> value (not a well-formed
    /// quoted base64 ETag — <see cref="RowVersionETag.FromIfMatch"/> throws
    /// <see cref="FormatException"/>) is rejected with <c>400 Bad Request</c>.
    /// </summary>
    [CoversRequirement("FR-014")]
    [CoversRequirement("FR-021")]
    [Fact]
    public async Task Patch_MemberRole_WithMalformedIfMatchHeader_ReturnsBadRequest()
    {
        await Factory.InitializeDatabaseAsync();
        var seed = await SeedAdministratorAndMemberAsync();

        using var adminClient = CreateAuthenticatedClient(seed.Administrator);

        using var request = new HttpRequestMessage(
            HttpMethod.Patch,
            $"/tenants/{seed.Administrator.TenantId.Value}/members/{seed.Member.UserId.Value}")
        {
            Content = JsonContent.Create(new { role = "Reader" }),
        };
        request.Headers.TryAddWithoutValidation("If-Match", "not-a-valid-etag");

        var response = await adminClient.SendAsync(request, TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.BadRequest);
    }

    /// <summary>
    /// <c>If-Match</c> handling, test 3: a well-formed but stale <c>If-Match</c> (doesn't match
    /// the membership's current <c>rowversion</c>) is rejected with <c>412 Precondition Failed</c>
    /// — the caller's view of the resource was out of date at request time.
    /// </summary>
    [CoversRequirement("FR-014")]
    [CoversRequirement("FR-021")]
    [Fact]
    public async Task Patch_MemberRole_WithStaleIfMatchHeader_ReturnsPreconditionFailed()
    {
        await Factory.InitializeDatabaseAsync();
        var seed = await SeedAdministratorAndMemberAsync();

        using var adminClient = CreateAuthenticatedClient(seed.Administrator);
        var staleIfMatch = RowVersionETag.ToETag([0, 0, 0, 0, 0, 0, 0, 1]);
        adminClient.DefaultRequestHeaders.Add("If-Match", staleIfMatch);

        var response = await adminClient.PatchAsJsonAsync(
            $"/tenants/{seed.Administrator.TenantId.Value}/members/{seed.Member.UserId.Value}",
            new { role = "Reader" },
            TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be((HttpStatusCode)412);
    }

    /// <summary>
    /// Not-found: the target <c>userId</c> has no active membership in the tenant — a genuinely
    /// unknown user id, never seeded as a member of this tenant at all — so the request is
    /// rejected with <c>404 Not Found</c>.
    /// </summary>
    [CoversRequirement("FR-014")]
    [Fact]
    public async Task Patch_MemberRole_ForUserWithNoActiveMembership_ReturnsNotFound()
    {
        await Factory.InitializeDatabaseAsync();
        var seed = await SeedAdministratorAndMemberAsync();

        using var adminClient = CreateAuthenticatedClient(seed.Administrator);
        var unknownUserId = UserId.New();

        var response = await adminClient.PatchAsJsonAsync(
            $"/tenants/{seed.Administrator.TenantId.Value}/members/{unknownUserId.Value}",
            new { role = "Reader" },
            TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.NotFound);
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
    /// Builds a valid <c>If-Match</c> value directly from the membership's current, persisted
    /// <c>RowVersion</c> — there is no per-member <c>GET</c> endpoint exposing an ETag for a
    /// single membership, so unlike the tenant-level PATCH's ETag round-trip, this reads the row
    /// straight from the database, mirroring <c>RolePermissionMatrixTests.GetMembershipIfMatchAsync</c>
    /// (T082).
    /// </summary>
    private async Task<string> GetMembershipIfMatchAsync(TenantId tenantId, MembershipId membershipId)
    {
        using var scope = Factory.Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<TenancyDbContext>();
        db.CurrentTenantId = tenantId;
        var membership = await db.Memberships.FindAsync(
            [membershipId], TestContext.Current.CancellationToken);
        return RowVersionETag.ToETag(membership!.RowVersion);
    }

    /// <summary>
    /// Seeds a single tenant with two distinct active members: an Administrator (the caller) and
    /// a separate Member (the target being role-changed). Mirrors
    /// <c>InviteAndManageMembersTests.SeedAdministratorAndMemberAsync</c> (T079) — that helper is
    /// <c>private</c> to its own file, so this is a local equivalent per the brief's guidance.
    /// </summary>
    private async Task<AdministratorAndMemberSeed> SeedAdministratorAndMemberAsync()
    {
        using var scope = Factory.Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<TenancyDbContext>();

        var tenant = Tenant.Create("Change Role Tenant");
        var admin = User.Create(
            entraTenantId: Guid.CreateVersion7(),
            entraObjectId: Guid.CreateVersion7(),
            email: new EmailAddress("admin@change-role-tenant.example.com"));
        var member = User.Create(
            entraTenantId: Guid.CreateVersion7(),
            entraObjectId: Guid.CreateVersion7(),
            email: new EmailAddress("member@change-role-tenant.example.com"));

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
    /// Seeds a single tenant with exactly one active <see cref="Role.Administrator"/> member —
    /// the sole-administrator-demotion-refusal test needs to attempt changing that administrator's
    /// own role. Mirrors <c>InviteAndManageMembersTests.SeedSoleAdministratorTenantAsync</c> (T079)
    /// — that helper is <c>private</c> to its own file, so this is a local equivalent.
    /// </summary>
    private async Task<SeededTenant> SeedSoleAdministratorTenantAsync()
    {
        using var scope = Factory.Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<TenancyDbContext>();

        var tenant = Tenant.Create("Sole Admin Change Role Tenant");
        var admin = User.Create(
            entraTenantId: Guid.CreateVersion7(),
            entraObjectId: Guid.CreateVersion7(),
            email: new EmailAddress("sole-admin@sole-admin-change-role-tenant.example.com"));

        db.Tenants.Add(tenant);
        db.Users.Add(admin);
        await db.SaveChangesAsync();

        db.CurrentTenantId = tenant.Id;
        var membership = Membership.Create(tenant.Id, admin.Id, Role.Administrator);
        db.Memberships.Add(membership);
        await db.SaveChangesAsync();

        return new SeededTenant(tenant.Id, admin.Id, membership.Id, admin.EntraTenantId, admin.EntraObjectId);
    }

    /// <summary>
    /// A single tenant seeded with two distinct active members: an Administrator (the caller) and
    /// a separate Member (the target). Both <see cref="SeededTenant"/> values share the same
    /// <c>TenantId</c>; only the user/membership/Entra identity fields differ.
    /// </summary>
    private sealed record AdministratorAndMemberSeed(SeededTenant Administrator, SeededTenant Member);
}
