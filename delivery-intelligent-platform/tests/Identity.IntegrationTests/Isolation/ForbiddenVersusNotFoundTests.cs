using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using ArchitectureTests.Support;
using Microsoft.Extensions.DependencyInjection;
using AwesomeAssertions;
using Identity.Domain.Abstractions;
using Identity.Domain.Memberships;
using Identity.Domain.Tenants;
using Identity.Domain.Users;
using Identity.Infrastructure.Persistence;
using Identity.IntegrationTests.Infrastructure;
using Xunit;

namespace Identity.IntegrationTests.Isolation;

/// <summary>
/// T082: the 403-versus-404 boundary — ADR-017's indistinguishability design (proven for
/// membership in T060) hinges on a non-member getting an identical, uninformative 404 for a
/// tenant it can't prove membership of, while a member who IS a member but lacks the right
/// role gets a distinct 403, because at that point there's no enumeration risk left (the
/// caller has already proven membership; it knows the tenant exists). Getting this backwards —
/// a wrong-role member also getting 404, or a non-member getting 403 — leaks tenant existence
/// through role refusals and defeats the whole point of T035/T060's work.
/// </summary>
/// <remarks>
/// <para>
/// <b>Representative operation, not the full matrix.</b> <c>POST /tenants/{tenantId}/invitations</c>
/// (administrator-only per FR-011/spec.md US3) is used as the single representative operation.
/// T081's <c>RolePermissionMatrixTests</c> already covers matrix breadth (invite/remove/rename/
/// list-invitations/revoke-invitation/list-members); this file's job is 403-vs-404 <b>depth</b> on
/// one of those surfaces, not repeating the matrix.
/// </para>
/// <para>
/// <b>Expected-red shape today (mirrors T081's documented failure shape).</b> No role-based
/// authorization exists anywhere in the codebase yet — that's deliberately T085/T088's job.
/// <c>POST /tenants/{tenantId}/invitations</c> already exists and already succeeds (201) for any
/// active member today, regardless of role. That means:
/// <list type="bullet">
/// <item><see cref="Post_Invitation_AsWrongRoleMember_Returns403"/> is <b>red</b> today: the
/// Member's request currently succeeds (201) instead of being refused (403) — same
/// "succeeds today, no check exists yet" shape as every non-administrator-refusal assertion in
/// T081's file.</item>
/// <item><see cref="Post_Invitation_ByNonMember_Returns404_AgainstTheSameTenant"/> is
/// <b>already green</b> today: T035's membership check (independent of role, predates T081/T082)
/// already produces 404 for a genuine non-member. This part isn't new.</item>
/// <item><see cref="Post_Invitation_ByAdministratorOfAnotherTenant_Returns404_NotForbidden"/> is
/// <b>already green</b> today for the same T035 reason — the caller has the right role, but not
/// for <i>this</i> tenant, so the tenant-membership check (not a role check) is what produces the
/// 404, and that check already exists.</item>
/// </list>
/// Once T085/T088 land, the first assertion goes green for the right reason too, and the whole
/// file continues to hold.
/// </para>
/// <para>
/// <b>Indistinguishability technique — reused from T060/T069, not invented here.</b> Per T060's
/// <see cref="TenantEndpointIsolationTests"/> and T069's <c>RevocationWindowTests</c>, a bare
/// status-code assertion in isolation doesn't prove non-enumerability; the 404 for a non-member
/// (or a wrong-tenant administrator) must be <b>byte-for-byte identical</b> to a known-good
/// reference 404 obtained against a syntactically-valid-but-never-seeded tenant id, using the
/// same caller and the same route/verb. Every 404 assertion below compares the full response body
/// against that reference, not just the status code.
/// </para>
/// <para>No production code changed by this task.</para>
/// </remarks>
public sealed class ForbiddenVersusNotFoundTests : IdentityIntegrationTestBase
{

    public ForbiddenVersusNotFoundTests(SqlServerFixture sqlServerFixture, ApiFactory factory)
        : base(sqlServerFixture, factory)
    {
    }

    /// <summary>
    /// Core assertion #1 (403 side): an active member of the tenant who is not an administrator
    /// attempts an administrator-only operation against their <b>own</b> tenant → 403, and that
    /// 403 must not leak anything beyond a generic forbidden refusal (no tenant display name, no
    /// other members' data, no hint distinguishing it from any other role-refusal).
    /// </summary>
    /// <remarks>
    /// Red today: <c>POST /tenants/{tenantId}/invitations</c> currently succeeds (201) for any
    /// active member — no role check exists until T085/T088.
    /// </remarks>
    [CoversRequirement("FR-008")]
    [CoversRequirement("FR-009")]
    [CoversRequirement("FR-018")]
    [Fact]
    public async Task Post_Invitation_AsWrongRoleMember_Returns403()
    {
        await Factory.InitializeDatabaseAsync();
        var seed = await SeedAdministratorAndMemberAsync();
        var otherSeed = await SeedAdministratorAndMemberAsync();

        using var memberClient = CreateAuthenticatedClient(seed.Member);

        var response = await PostInvitationAsync(memberClient, seed.Administrator.TenantId.Value);

        // Reference: a different wrong-role member, refused for the identical operation against
        // their own (different) tenant — same caller-shape (active member, wrong role, own
        // tenant), different identity and tenant entirely. If the 403 body is genuinely generic,
        // it must be byte-for-byte identical regardless of which tenant/caller produced it.
        using var otherMemberClient = CreateAuthenticatedClient(otherSeed.Member);
        var referenceResponse = await PostInvitationAsync(
            otherMemberClient, otherSeed.Administrator.TenantId.Value);

        response.StatusCode.Should().Be(HttpStatusCode.Forbidden);
        referenceResponse.StatusCode.Should().Be(HttpStatusCode.Forbidden);

        var body = await response.Content.ReadAsStringAsync(TestContext.Current.CancellationToken);
        var referenceBody = await referenceResponse.Content.ReadAsStringAsync(
            TestContext.Current.CancellationToken);

        // Primary rigor check — byte-for-byte indistinguishability, mirroring the 404 tests'
        // technique: a 403 for this specific wrong-role-member-vs-tenant pairing must be
        // identical to a 403 produced by an entirely different wrong-role member against an
        // entirely different tenant. Any divergence would mean the response is leaking
        // caller- or tenant-specific detail through the "generic" refusal.
        body.Should().Be(referenceBody);

        // Belt-and-suspenders substring checks retained for readability/failure diagnostics.
        body.Should().NotContain(seed.Administrator.EntraObjectId.ToString());
        body.Should().NotContain("Administrator And Member Tenant (403 vs 404)");
    }

    /// <summary>
    /// Core assertion #2 (404 side): a caller who is not a member at all of the tenant — never
    /// seeded anywhere — attempts the identical operation against the identical tenant id → 404,
    /// byte-for-byte identical to the known-good reference 404 (same caller, same route/verb,
    /// against a never-seeded tenant id). This is the part T035's membership check already
    /// covers; expected green today.
    /// </summary>
    [CoversRequirement("FR-008")]
    [CoversRequirement("FR-009")]
    [Fact]
    public async Task Post_Invitation_ByNonMember_Returns404_AgainstTheSameTenant()
    {
        await Factory.InitializeDatabaseAsync();
        var seed = await SeedAdministratorAndMemberAsync();

        using var nonMemberClient = CreateAuthenticatedClient(NeverSeededCaller());

        var againstRealTenant = await PostInvitationAsync(
            nonMemberClient, seed.Administrator.TenantId.Value);

        var neverSeededTenantId = Guid.NewGuid();
        var referenceResponse = await PostInvitationAsync(nonMemberClient, neverSeededTenantId);

        // Assert: refused, not a leak, and not confused with a role-refusal.
        againstRealTenant.StatusCode.Should().Be(HttpStatusCode.NotFound);
        againstRealTenant.StatusCode.Should().NotBe(HttpStatusCode.OK);
        againstRealTenant.StatusCode.Should().NotBe(HttpStatusCode.Created);
        againstRealTenant.StatusCode.Should().NotBe(HttpStatusCode.Forbidden);

        // Assert: byte-for-byte indistinguishable from the reference never-seeded-tenant 404 —
        // a real tenant the caller isn't a member of must look identical to one that doesn't
        // exist at all.
        referenceResponse.StatusCode.Should().Be(againstRealTenant.StatusCode);
        var realBody = await againstRealTenant.Content.ReadAsStringAsync(TestContext.Current.CancellationToken);
        var referenceBody = await referenceResponse.Content.ReadAsStringAsync(TestContext.Current.CancellationToken);
        realBody.Should().Be(referenceBody);
    }

    /// <summary>
    /// Requirement 3 — the boundary the other direction (candidate-tenant-selector attack): a
    /// caller who has the <b>correct</b> role (Administrator) for the operation, but is
    /// substituting a <b>different</b> tenant's id — one they are not a member of at all — must
    /// still get 404, never 403. From that other tenant's perspective the caller genuinely isn't
    /// a member; role is irrelevant until membership for *that specific tenant* is established.
    /// Already green today via T035's membership check (predates any role check).
    /// </summary>
    [CoversRequirement("FR-008")]
    [CoversRequirement("FR-009")]
    [Fact]
    public async Task Post_Invitation_ByAdministratorOfAnotherTenant_Returns404_NotForbidden()
    {
        await Factory.InitializeDatabaseAsync();
        var tenantOne = await SeedAdministratorAndMemberAsync();
        var tenantTwo = await SeedAdministratorAndMemberAsync();

        // TenantOne's Administrator substitutes TenantTwo's id into the URL — legitimate
        // administrator of their own tenant, not a member of TenantTwo at all.
        using var administratorClient = CreateAuthenticatedClient(tenantOne.Administrator);

        var wrongTenantResponse = await PostInvitationAsync(
            administratorClient, tenantTwo.Administrator.TenantId.Value);

        var neverSeededTenantId = Guid.NewGuid();
        var referenceResponse = await PostInvitationAsync(administratorClient, neverSeededTenantId);

        wrongTenantResponse.StatusCode.Should().Be(HttpStatusCode.NotFound);
        wrongTenantResponse.StatusCode.Should().NotBe(HttpStatusCode.Forbidden);
        wrongTenantResponse.StatusCode.Should().NotBe(HttpStatusCode.Created);

        referenceResponse.StatusCode.Should().Be(wrongTenantResponse.StatusCode);
        var wrongTenantBody = await wrongTenantResponse.Content.ReadAsStringAsync(
            TestContext.Current.CancellationToken);
        var referenceBody = await referenceResponse.Content.ReadAsStringAsync(
            TestContext.Current.CancellationToken);
        wrongTenantBody.Should().Be(referenceBody);
    }

    private static Task<HttpResponseMessage> PostInvitationAsync(HttpClient client, Guid tenantId)
    {
        var request = new HttpRequestMessage(HttpMethod.Post, $"/tenants/{tenantId}/invitations")
        {
            Content = JsonContent.Create(new
            {
                email = $"probe-{Guid.NewGuid()}@forbidden-vs-not-found.example.com",
                role = "Member",
            }),
        };
        request.Headers.Add("Idempotency-Key", Guid.NewGuid().ToString());
        return client.SendAsync(request, TestContext.Current.CancellationToken);
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
    /// A caller with credentials that were never persisted anywhere — no <see cref="User"/>, no
    /// <see cref="Membership"/>, in any tenant. <see cref="SeededTenant.TenantId"/>/
    /// <see cref="SeededTenant.UserId"/>/<see cref="SeededTenant.MembershipId"/> are irrelevant
    /// for this caller (never looked up); only the Entra identity fields are used to authenticate.
    /// </summary>
    private static SeededTenant NeverSeededCaller() =>
        new(TenantId.New(), UserId.New(), MembershipId.New(), Guid.CreateVersion7(), Guid.CreateVersion7());

    /// <summary>
    /// Seeds a single tenant with exactly one active <see cref="Role.Administrator"/> and one
    /// active <see cref="Role.Member"/> — local equivalent of T081's
    /// <c>RolePermissionMatrixTests.SeedAdministratorAndMemberAsync</c>, which is <c>private</c>
    /// to that class and therefore inaccessible from here. Uses a distinct tenant display name
    /// per call (via a fresh <see cref="Guid"/> suffix) so the two tenants seeded by
    /// <see cref="Post_Invitation_ByAdministratorOfAnotherTenant_Returns404_NotForbidden"/> are
    /// never confusable with each other in a body-comparison assertion.
    /// </summary>
    private async Task<AdministratorAndMemberSeed> SeedAdministratorAndMemberAsync()
    {
        using var scope = Factory.Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<IdentityDbContext>();

        var suffix = Guid.NewGuid();
        var tenant = Tenant.Create($"Administrator And Member Tenant (403 vs 404) {suffix}");
        var admin = User.Create(
            entraTenantId: Guid.CreateVersion7(),
            entraObjectId: Guid.CreateVersion7(),
            email: new EmailAddress($"admin-{suffix}@forbidden-vs-not-found.example.com"));
        var member = User.Create(
            entraTenantId: Guid.CreateVersion7(),
            entraObjectId: Guid.CreateVersion7(),
            email: new EmailAddress($"member-{suffix}@forbidden-vs-not-found.example.com"));

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

    private sealed record AdministratorAndMemberSeed(SeededTenant Administrator, SeededTenant Member);
}
