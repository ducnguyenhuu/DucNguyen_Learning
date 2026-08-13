using System.Net;
using System.Net.Http.Headers;
using AwesomeAssertions;
using Microsoft.Extensions.DependencyInjection;
using Tenancy.Domain.Abstractions;
using Tenancy.Domain.Memberships;
using Tenancy.Domain.Tenants;
using Tenancy.Domain.Users;
using Tenancy.Infrastructure.Persistence;
using Tenancy.IntegrationTests.Infrastructure;
using Xunit;

namespace Tenancy.IntegrationTests.Scenarios;

/// <summary>
/// Failing tests (T069) that document the accepted revocation-staleness trade-off from
/// spec.md's Assumption 7 and FR-016: "Credentials are short-lived enough that revoked access
/// ends within one hour, satisfying FR-016 without per-request revocation checks." This file
/// proves <b>both halves</b> of that trade-off, not just the convenient one.
/// </summary>
/// <remarks>
/// <para>
/// <b>Half 1 (instantaneous):</b> once a member is removed, any <b>newly issued</b> auth context
/// for them is refused immediately, going forward — not because the token becomes stale, but
/// because <c>TenantContextResolutionMiddleware</c> (T035) checks the current
/// <see cref="MembershipStatus"/> against the database on every request, not the token's claims.
/// A removed member must be indistinguishable (ADR-017/FR-009) from a caller who was never a
/// member at all — the same 404 either way.
/// </para>
/// <para>
/// <b>Half 2 (deliberately not instantaneous):</b> a token already issued <i>before</i> removal,
/// and not yet expired, is not rejected on revocation grounds. The system does not maintain a
/// token blocklist; FR-016 is satisfied by the token's own short expiry, not by active
/// revocation. This half is proven with <see cref="SignedTokenHarness"/> (Phase 3, T041/T047) —
/// a real, RSA-signed JWT run through the genuine <c>JwtBearer</c> pipeline — because only a
/// real signed token can prove "the token itself was not the reason for any refusal."
/// <see cref="TestAuthHandler"/> (Tier 1) is structurally incapable of proving this: it never
/// exercises token validation at all, so a passing Tier-1 test could not distinguish "the token
/// wasn't blocklisted" from "there is no token validation happening in the first place."
/// </para>
/// <para>
/// <b>Today's expected failure mode.</b> <c>DELETE /tenants/{tenantId}/members/{userId}</c>
/// (T079) does not exist yet, so every removal attempt below hits ASP.NET Core's own
/// "no matching endpoint" 404/405 instead of a real removal — consistent with the established
/// precedent in <see cref="Isolation.MembershipEndpointIsolationTests"/> (T062),
/// <see cref="InviteAndManageMembersTests"/> (T063), and
/// <see cref="ConcurrentAdminRemovalTests"/> (T068). Because the removal itself cannot succeed
/// today, the membership row is never actually transitioned to
/// <see cref="MembershipStatus.Removed"/>, so Test 1's "refused" assertion and Test 2's
/// "not rejected for token reasons" assertion are both currently unfalsifiable by the real
/// mechanism they target — they encode the target spec and will only become meaningful proofs
/// once T079 (the endpoint) and, for Test 1, the already-implemented T035 middleware are wired
/// together end to end.
/// </para>
/// </remarks>
public sealed class RevocationWindowTests : IClassFixture<ApiFactory>
{
    private readonly ApiFactory _factory;

    public RevocationWindowTests(SqlServerFixture sqlServerFixture, ApiFactory factory)
    {
        _factory = factory;
        _factory.UseConnectionString(sqlServerFixture.ConnectionString);
    }

    /// <summary>
    /// Half 1: after removal, a fresh authenticated request from the removed member is refused,
    /// and that refusal is byte-for-byte indistinguishable (status + body) from the refusal a
    /// caller who was <b>never</b> a member of the tenant gets for the identical request — per
    /// FR-009/ADR-017, a 403 here would itself leak "you used to have access," so it must be the
    /// same 404 either way.
    /// </summary>
    [Fact]
    public async Task RemovedMember_FreshRequest_IsRefused_AndIndistinguishableFromNeverAMember()
    {
        await _factory.InitializeDatabaseAsync();
        var seed = await SeedAdministratorAndMemberAsync();

        using var adminClient = CreateTestSchemeClient(seed.Administrator);

        // Target-spec removal. Today this hits an absent route (T079 not yet implemented).
        var deleteResponse = await adminClient.DeleteAsync(
            $"/tenants/{seed.Administrator.TenantId.Value}/members/{seed.Member.UserId.Value}",
            TestContext.Current.CancellationToken);
        deleteResponse.StatusCode.Should().Be(HttpStatusCode.NoContent);

        // The just-removed member presents a brand new authenticated context (fresh
        // TestAuthHandler identity, standing in for "signs in again") and attempts to read the
        // tenant they used to belong to.
        using var removedMemberClient = CreateTestSchemeClient(seed.Member);
        var removedMemberResponse = await removedMemberClient.GetAsync(
            $"/tenants/{seed.Administrator.TenantId.Value}",
            TestContext.Current.CancellationToken);

        // A caller who was genuinely never a member of this tenant, making the exact same
        // request.
        using var strangerClient = _factory.CreateClient();
        strangerClient.DefaultRequestHeaders.Authorization =
            new AuthenticationHeaderValue("TestScheme", "test");
        strangerClient.DefaultRequestHeaders.Add("X-Test-Oid", Guid.NewGuid().ToString());
        strangerClient.DefaultRequestHeaders.Add("X-Test-Tid", Guid.NewGuid().ToString());
        var strangerResponse = await strangerClient.GetAsync(
            $"/tenants/{seed.Administrator.TenantId.Value}",
            TestContext.Current.CancellationToken);

        removedMemberResponse.StatusCode.Should().Be(HttpStatusCode.NotFound);
        removedMemberResponse.StatusCode.Should().NotBe(HttpStatusCode.OK);
        removedMemberResponse.StatusCode.Should().NotBe(HttpStatusCode.Forbidden);

        // Indistinguishability: the removed member's refusal must look exactly like the
        // never-a-member stranger's refusal — same status, same (empty) body.
        removedMemberResponse.StatusCode.Should().Be(strangerResponse.StatusCode);
        var removedMemberBody = await removedMemberResponse.Content.ReadAsStringAsync(
            TestContext.Current.CancellationToken);
        var strangerBody = await strangerResponse.Content.ReadAsStringAsync(
            TestContext.Current.CancellationToken);
        removedMemberBody.Should().Be(strangerBody);
    }

    /// <summary>
    /// Half 2: a token minted <b>before</b> removal, still cryptographically unexpired, is
    /// replayed <b>after</b> removal. Asserts the token itself is not the reason for any
    /// refusal: FR-016/Assumption 7 is deliberately satisfied by expiry, not by a blocklist, so
    /// this must never come back <c>401 Unauthorized</c> (the status openapi.yaml reserves
    /// exclusively for "no token, or a token that fails validation" — see contracts/openapi.yaml's
    /// status code contract table). If membership is genuinely gone by the time this replay
    /// happens, the correct refusal is the same ADR-017 404 Test 1 uses (a membership problem,
    /// not a token problem) — never 401.
    /// </summary>
    [Fact]
    public async Task AlreadyIssuedToken_ReplayedAfterRemoval_IsNotRejectedOnTokenGrounds()
    {
        await _factory.InitializeDatabaseAsync();
        var seed = await SeedAdministratorAndMemberAsync();

        // Mint a genuinely valid, unexpired, real RSA-signed JWT for the member BEFORE removal —
        // the same harness/host trust relationship T047's TokenValidationTests uses, so this
        // token goes through the real JwtBearer pipeline, not TestAuthHandler.
        var memberToken = _factory.TokenHarness.MintToken(
            tid: seed.Member.EntraTenantId,
            oid: seed.Member.EntraObjectId,
            audience: ApiFactory.ExpectedAudience,
            issuer: ApiFactory.ExpectedIssuer);

        using var adminClient = CreateTestSchemeClient(seed.Administrator);

        // Target-spec removal. Today this hits an absent route (T079 not yet implemented), so
        // the membership row is never actually transitioned — meaning today's replay below
        // reaches a still-active membership regardless. That is fine: the assertion below (never
        // 401) is designed to hold in both states, because it targets "was the token itself the
        // reason," not "what exact status this endpoint returns" — see the class remarks and the
        // report's flagged ambiguity for why a stronger, single-status assertion was avoided.
        var deleteResponse = await adminClient.DeleteAsync(
            $"/tenants/{seed.Administrator.TenantId.Value}/members/{seed.Member.UserId.Value}",
            TestContext.Current.CancellationToken);
        deleteResponse.StatusCode.Should().Be(HttpStatusCode.NoContent);

        using var replayClient = _factory.CreateClient();
        replayClient.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", memberToken);

        var replayResponse = await replayClient.GetAsync(
            $"/tenants/{seed.Administrator.TenantId.Value}",
            TestContext.Current.CancellationToken);

        // The token itself was never the reason for any refusal — this system does not
        // blocklist. Any refusal must come from the (separate, already-instantaneous)
        // membership check, never from token validation.
        replayResponse.StatusCode.Should().NotBe(HttpStatusCode.Unauthorized);
    }

    private HttpClient CreateTestSchemeClient(SeededTenant seededTenant)
    {
        var client = _factory.CreateClient();
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("TestScheme", "test");
        client.DefaultRequestHeaders.Add("X-Test-Oid", seededTenant.EntraObjectId.ToString());
        client.DefaultRequestHeaders.Add("X-Test-Tid", seededTenant.EntraTenantId.ToString());
        return client;
    }

    /// <summary>
    /// Seeds a single tenant with one active <see cref="Role.Administrator"/> (the remover) and
    /// one active <see cref="Role.Member"/> (the removee) — the same minimal shape
    /// <see cref="InviteAndManageMembersTests"/>'s local helper of the same name uses, duplicated
    /// here (rather than shared) because <see cref="ApiFactory"/> exposes no admin+member seed
    /// method and this file should not reach into a sibling test class's private helper.
    /// </summary>
    private async Task<AdministratorAndMemberSeed> SeedAdministratorAndMemberAsync()
    {
        using var scope = _factory.Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<TenancyDbContext>();

        var tenant = Tenant.Create("Revocation Window Tenant");
        var admin = User.Create(
            entraTenantId: Guid.CreateVersion7(),
            entraObjectId: Guid.CreateVersion7(),
            email: new EmailAddress("admin@revocation-window-tenant.example.com"));
        var member = User.Create(
            entraTenantId: Guid.CreateVersion7(),
            entraObjectId: Guid.CreateVersion7(),
            email: new EmailAddress("member@revocation-window-tenant.example.com"));

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
