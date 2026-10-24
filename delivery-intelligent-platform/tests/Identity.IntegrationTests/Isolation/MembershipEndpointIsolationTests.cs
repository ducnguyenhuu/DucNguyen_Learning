using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using ArchitectureTests.Support;
using AwesomeAssertions;
using Identity.IntegrationTests.Infrastructure;
using Xunit;

namespace Identity.IntegrationTests.Isolation;

/// <summary>
/// Failing isolation tests (T062) for every tenant-scoped invitation/membership endpoint Phase 4
/// (User Story 2) will add: <c>POST /tenants/{tenantId}/invitations</c>,
/// <c>GET /tenants/{tenantId}/invitations</c>,
/// <c>DELETE /tenants/{tenantId}/invitations/{invitationId}</c>,
/// <c>GET /tenants/{tenantId}/members</c>, and
/// <c>DELETE /tenants/{tenantId}/members/{userId}</c>. <c>POST /invitations/{token}/accept</c> is
/// deliberately excluded — per ADR-017 it is not tenant-scoped, and is covered separately by
/// T064.
/// </summary>
/// <remarks>
/// <b>None of these routes exist yet.</b> This file is written before Phase 4's implementation
/// (T070-T080), following the exact tests-first pattern Phase 3 used for
/// <see cref="TenantEndpointIsolationTests"/> (T044) and <see cref="CrossTenantReadRefusedTests"/>
/// (T043). Every assertion here currently passes only because ASP.NET Core's own routing
/// middleware returns a plain "no matching endpoint" 404 for an unregistered route — not because
/// any real tenant-scoping logic (<c>.WithTenantContextResolution()</c>) has run. That is the
/// expected, correct state for this task. Once T070+ adds the real endpoints, each test here
/// should be revisited the same way T060 revisited <see cref="TenantEndpointIsolationTests"/>:
/// prove the 404 survives, then prove it comes from a genuine membership check (e.g. by
/// temporarily disabling <c>IdentityDbContext</c>'s <c>"TenantFilter"</c> and confirming the test
/// starts failing on a real cross-tenant leak) before trusting it as isolation coverage.
/// </remarks>
public sealed class MembershipEndpointIsolationTests : IdentityIntegrationTestBase
{

    public MembershipEndpointIsolationTests(SqlServerFixture sqlServerFixture, ApiFactory factory)
        : base(sqlServerFixture, factory)
    {
    }

    [CoversRequirement("FR-008")]
    [Fact]
    public async Task Post_InvitationForOtherTenant_IsRefused()
    {
        await Factory.InitializeDatabaseAsync();
        var seed = await Factory.SeedTwoTenantsAsync();

        using var client = CreateAuthenticatedClientAsTenantAMember(seed);
        client.DefaultRequestHeaders.Add("Idempotency-Key", Guid.NewGuid().ToString());

        // Tenant A's member attempts to invite someone into Tenant B via Tenant A's route
        // parameter mismatch: the route's {tenantId} is Tenant B's, but the caller only has an
        // active membership in Tenant A.
        var response = await client.PostAsJsonAsync(
            $"/tenants/{seed.TenantB.TenantId.Value}/invitations",
            new { email = "new-invitee@tenant-b.example.com", role = "Member" },
            TestContext.Current.CancellationToken);

        AssertRefusedNotFound(response);
    }

    [CoversRequirement("FR-008")]
    [Fact]
    public async Task Get_InvitationsForOtherTenant_IsRefused()
    {
        await Factory.InitializeDatabaseAsync();
        var seed = await Factory.SeedTwoTenantsAsync();

        using var client = CreateAuthenticatedClientAsTenantAMember(seed);

        var response = await client.GetAsync(
            $"/tenants/{seed.TenantB.TenantId.Value}/invitations",
            TestContext.Current.CancellationToken);

        AssertRefusedNotFound(response);
    }

    [CoversRequirement("FR-008")]
    [Fact]
    public async Task Delete_InvitationForOtherTenant_IsRefused()
    {
        await Factory.InitializeDatabaseAsync();
        // A genuinely-persisted, still-pending invitation in Tenant B, so the refusal proves
        // route-level tenant scoping — not merely that the invitation id happens not to exist.
        var seed = await Factory.SeedTwoTenantsWithInvitationInTenantBAsync();

        using var client = CreateAuthenticatedClientAsTenantAMember(seed.TenantA);

        var response = await client.DeleteAsync(
            $"/tenants/{seed.TenantB.TenantId.Value}/invitations/{seed.InvitationId.Value}",
            TestContext.Current.CancellationToken);

        AssertRefusedNotFound(response);
    }

    [CoversRequirement("FR-008")]
    [Fact]
    public async Task Get_MembersForOtherTenant_IsRefused()
    {
        await Factory.InitializeDatabaseAsync();
        var seed = await Factory.SeedTwoTenantsAsync();

        using var client = CreateAuthenticatedClientAsTenantAMember(seed);

        var response = await client.GetAsync(
            $"/tenants/{seed.TenantB.TenantId.Value}/members",
            TestContext.Current.CancellationToken);

        AssertRefusedNotFound(response);
    }

    [CoversRequirement("FR-008")]
    [Fact]
    public async Task Delete_MemberForOtherTenant_IsRefused()
    {
        await Factory.InitializeDatabaseAsync();
        // Tenant B's own real member (SeededTenant.UserId), being removed via Tenant A's route
        // context — the point is proving the route refuses regardless of the target user
        // legitimately existing as a Tenant B member.
        var seed = await Factory.SeedTwoTenantsAsync();

        using var client = CreateAuthenticatedClientAsTenantAMember(seed);

        var response = await client.DeleteAsync(
            $"/tenants/{seed.TenantB.TenantId.Value}/members/{seed.TenantB.UserId.Value}",
            TestContext.Current.CancellationToken);

        AssertRefusedNotFound(response);
    }

    private static void AssertRefusedNotFound(HttpResponseMessage response)
    {
        // Per ADR-017, cross-tenant access should be indistinguishable from "doesn't exist" —
        // not a 200 (leak) and not a distinguishing 403 (which would itself leak existence).
        response.StatusCode.Should().Be(HttpStatusCode.NotFound);
        response.StatusCode.Should().NotBe(HttpStatusCode.OK);
        response.StatusCode.Should().NotBe(HttpStatusCode.Forbidden);
    }

    private HttpClient CreateAuthenticatedClientAsTenantAMember(TwoTenantSeed seed) =>
        CreateAuthenticatedClientAsTenantAMember(seed.TenantA);

    private HttpClient CreateAuthenticatedClientAsTenantAMember(SeededTenant tenantA)
    {
        var client = Factory.CreateClient();
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("TestScheme", "test");
        client.DefaultRequestHeaders.Add("X-Test-Oid", tenantA.EntraObjectId.ToString());
        client.DefaultRequestHeaders.Add("X-Test-Tid", tenantA.EntraTenantId.ToString());
        return client;
    }
}
