using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using ArchitectureTests.Support;
using AwesomeAssertions;
using Identity.IntegrationTests.Infrastructure;
using Xunit;

namespace Identity.IntegrationTests.Isolation;

/// <summary>
/// Exhaustive, dedicated ADR-017-exception coverage for the three endpoints that are
/// deliberately unscoped by tenant: <c>POST /tenants</c> (no tenant context exists yet at
/// creation time), <c>GET /tenants</c> (the one legitimate cross-tenant read in the whole
/// system, backed by T037's audited <c>MembershipDirectory</c>), and
/// <c>POST /invitations/{token}/accept</c> (the caller has no membership yet — creating one is
/// the point). Distinct from T044/T045's lighter coverage of the first two endpoints in
/// <see cref="TenantEndpointIsolationTests"/> and <see cref="CrossTenantReadRefusedTests"/>, and
/// from T063's scenario-level coverage of accept in
/// <see cref="Scenarios.InviteAndManageMembersTests"/>.
/// </summary>
/// <remarks>
/// Neither <c>POST /tenants</c> nor <c>GET /tenants</c> exists yet (T058 adds them), so every
/// request below against those two currently hits a route absent from <c>Program.cs</c>'s route
/// table and gets a plain ASP.NET Core routing 404. These tests are written as the target spec —
/// <c>POST /tenants</c> should succeed (201) once implemented, and <c>GET /tenants</c> should
/// return only the caller's own tenants. Noted briefly per task instructions; moving on.
/// <para>
/// ADR-017 exception 3 — <c>POST /invitations/{token}/accept</c> — is unscoped for the same
/// structural reason as <c>POST /tenants</c>: there is no membership yet for
/// <c>TenantContextResolutionMiddleware</c>'s route-selector validation to check against. But
/// its authorization model is different from every other route in this system, including
/// <c>POST /tenants</c>: it is not "any authenticated user" and it is not "route selector
/// validated against membership" — it is the opaque token itself, <em>plus</em> an identity
/// match (FR-013). Knowing a valid, unexpired token is necessary but not sufficient; the
/// authenticated caller's email must equal the address the invitation was issued to. Per
/// <c>contracts/openapi.yaml</c>, a token belonging to someone else yields 403 (the token is
/// valid, the caller simply is not its subject) — distinct from the 404 used for unknown,
/// expired, revoked, or already-accepted tokens, so token validity itself can't be probed. This
/// route also doesn't exist yet, so both tests below currently hit the same absent-route 404;
/// the wrong-identity case is written to the target 403 and is therefore expected-red today,
/// following the same precedent T063 already established for this exact scenario.
/// </para>
/// </remarks>
public sealed class UnscopedOperationTests : IdentityIntegrationTestBase
{

    public UnscopedOperationTests(SqlServerFixture sqlServerFixture, ApiFactory factory)
        : base(sqlServerFixture, factory)
    {
    }

    [CoversRequirement("FR-005")]
    [Fact]
    public async Task Post_Tenants_WithoutAnyTenantContext_Succeeds()
    {
        await Factory.InitializeDatabaseAsync();
        await Factory.SeedTwoTenantsAsync();

        // A brand-new, never-seeded Entra identity — there is no membership-based gate on
        // this route, so tenant creation must work even though the caller has no tenant
        // context established yet.
        using var client = Factory.CreateClient();
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("TestScheme", "test");
        client.DefaultRequestHeaders.Add("X-Test-Oid", Guid.NewGuid().ToString());
        client.DefaultRequestHeaders.Add("X-Test-Tid", Guid.NewGuid().ToString());
        client.DefaultRequestHeaders.Add("Idempotency-Key", Guid.NewGuid().ToString());

        var response = await client.PostAsync(
            "/tenants",
            JsonContent("Brand New Tenant"),
            TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.Created);
    }

    [Fact]
    public async Task Get_Tenants_ForTenantAMember_ReturnsOnlyTenantA_NotTenantB()
    {
        await Factory.InitializeDatabaseAsync();
        var seed = await Factory.SeedTwoTenantsAsync();

        using var client = CreateAuthenticatedClient(seed.TenantA.EntraObjectId, seed.TenantA.EntraTenantId);

        var response = await client.GetAsync("/tenants", TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.OK);

        var body = await response.Content.ReadAsStringAsync(TestContext.Current.CancellationToken);

        body.Should().Contain(seed.TenantA.TenantId.Value.ToString());
        body.Should().NotContain(seed.TenantB.TenantId.Value.ToString());
        body.Should().NotContain("Tenant B");
    }

    [Fact]
    public async Task Get_Tenants_ForUserWithNoMemberships_ReturnsEmptyArray()
    {
        await Factory.InitializeDatabaseAsync();
        await Factory.SeedTwoTenantsAsync();

        // A fresh, never-seeded Entra identity with no memberships anywhere.
        using var client = CreateAuthenticatedClient(Guid.NewGuid(), Guid.NewGuid());

        var response = await client.GetAsync("/tenants", TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.OK);

        var payload = await response.Content.ReadFromJsonAsync<object[]>(
            TestContext.Current.CancellationToken);

        payload.Should().NotBeNull();
        payload.Should().BeEmpty();
    }

    /// <summary>
    /// ADR-017 exception 3, refusal branch: a caller who holds a valid, unexpired token for
    /// an invitation issued to someone else's email cannot accept it by authenticating as a
    /// different identity. This is FR-013's core assertion — the token alone is not enough.
    /// Distinct from <see cref="Scenarios.InviteAndManageMembersTests.Post_AcceptInvitation_AsDifferentEmailThanInvited_IsRefused"/>
    /// (which asserts the same rule at the scenario level with an arbitrary token string); this
    /// test anchors the assertion to a genuinely-persisted, still-pending invitation.
    /// </summary>
    [CoversRequirement("FR-013")]
    [Fact]
    public async Task Post_AcceptInvitation_WithValidTokenForSomeoneElse_IsRefused()
    {
        await Factory.InitializeDatabaseAsync();
        var seed = await Factory.SeedTwoTenantsWithInvitationInTenantBAsync();

        // The seeded invitation is addressed to invitee@tenant-b.example.com. This caller is a
        // real, distinct identity (Tenant A's seeded member) authenticating with a different
        // email — a valid token belonging to somebody else does not authorize acceptance.
        using var client = Factory.CreateClient();
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("TestScheme", "test");
        client.DefaultRequestHeaders.Add("X-Test-Oid", seed.TenantA.EntraObjectId.ToString());
        client.DefaultRequestHeaders.Add("X-Test-Tid", seed.TenantA.EntraTenantId.ToString());
        client.DefaultRequestHeaders.Add("X-Test-Email", "member-a@tenant-a.example.com");

        var response = await client.PostAsync(
            "/invitations/some-valid-token-for-tenant-b-invitee/accept",
            content: null,
            TestContext.Current.CancellationToken);

        // Target spec is 403 per contracts/openapi.yaml (token valid, wrong subject). The
        // endpoint doesn't exist yet, so this is currently a plain routing 404 and expected-red,
        // matching T063's precedent for this exact scenario.
        response.StatusCode.Should().Be(HttpStatusCode.Forbidden);
    }

    /// <summary>
    /// ADR-017 exception 3, success branch: the invitation's actual addressee, authenticated
    /// with the matching email and holding the valid token, can accept it despite having no
    /// prior membership anywhere — that's the entire point of leaving this route unscoped.
    /// </summary>
    [CoversRequirement("FR-012")]
    [Fact]
    public async Task Post_AcceptInvitation_AsInvitedAddressee_Succeeds()
    {
        await Factory.InitializeDatabaseAsync();
        var seed = await Factory.SeedTwoTenantsWithInvitationInTenantBAsync();

        // A brand-new identity — never seeded as a member anywhere — authenticating with the
        // exact email the invitation was issued to.
        using var client = Factory.CreateClient();
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("TestScheme", "test");
        client.DefaultRequestHeaders.Add("X-Test-Oid", Guid.NewGuid().ToString());
        client.DefaultRequestHeaders.Add("X-Test-Tid", Guid.NewGuid().ToString());
        client.DefaultRequestHeaders.Add("X-Test-Email", "invitee@tenant-b.example.com");

        var response = await client.PostAsync(
            "/invitations/some-valid-token-for-tenant-b-invitee/accept",
            content: null,
            TestContext.Current.CancellationToken);

        // Target spec is 200 once implemented; today this is a plain routing 404, per the
        // file's own documented "not implemented yet" disclosure pattern.
        response.StatusCode.Should().Be(HttpStatusCode.OK);
    }

    private HttpClient CreateAuthenticatedClient(Guid entraObjectId, Guid entraTenantId)
    {
        var client = Factory.CreateClient();
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("TestScheme", "test");
        client.DefaultRequestHeaders.Add("X-Test-Oid", entraObjectId.ToString());
        client.DefaultRequestHeaders.Add("X-Test-Tid", entraTenantId.ToString());
        return client;
    }

    private static JsonContent JsonContent(object displayName) =>
        System.Net.Http.Json.JsonContent.Create(new { displayName });
}
