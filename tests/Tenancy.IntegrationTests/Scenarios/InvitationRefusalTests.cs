using System.Net;
using System.Net.Http.Headers;
using Microsoft.Extensions.DependencyInjection;
using AwesomeAssertions;
using Tenancy.Domain.Abstractions;
using Tenancy.Domain.Invitations;
using Tenancy.Domain.Tenants;
using Tenancy.Infrastructure.Persistence;
using Tenancy.IntegrationTests.Infrastructure;
using Xunit;

namespace Tenancy.IntegrationTests.Scenarios;

/// <summary>
/// T065: dedicated 404-family indistinguishability coverage for
/// <c>POST /invitations/{token}/accept</c>. Per <c>contracts/openapi.yaml</c> and ADR-017's core
/// indistinguishability principle (already proven for tenant membership in T035/T060), a caller
/// must not be able to distinguish, from the HTTP response alone, <i>why</i> an invitation token
/// didn't work. An unknown token, an expired token, a revoked token, and an already-accepted
/// token must all collapse into the identical <c>404 Not Found</c> — never a different code that
/// would let a caller probe token validity or invitation history.
/// </summary>
/// <remarks>
/// <b>Scope boundary with T064.</b> T064 (<see cref="Isolation.UnscopedOperationTests"/>) covers
/// the one case that is deliberately kept <i>distinguishable</i> from this 404 family: a valid,
/// unexpired token presented by the wrong identity, which the contract maps to <c>403</c> because
/// the token itself was genuinely valid. This file covers everything else — every case where the
/// token itself can never again succeed, for whatever reason — which must all look identical.
/// <para>
/// <b>What this file proves right now, and what it doesn't.</b> Same caveat as
/// <see cref="EstablishTenantTests"/> (T045) and <see cref="Scenarios.InviteAndManageMembersTests"/>
/// (T063): <c>POST /invitations/{token}/accept</c> doesn't exist yet (T070-T080 add it), so every
/// request below hits a route absent from <c>Program.cs</c>'s route table and gets ASP.NET Core's
/// own "no matching endpoint" 404 — not any real business rule. All four assertions below happen
/// to already pass today for that wrong reason; they are kept as the target spec so they remain
/// green, for the <i>right</i> reason, once the endpoint lands.
/// </para>
/// <para>
/// <b>How "revoked" is modeled.</b> <see cref="Invitation"/> already exposes a genuine
/// <see cref="Invitation.Revoke"/> domain operation (transitioning to
/// <see cref="InvitationStatus.Revoked"/>), so the revoked-token test below calls it directly
/// through the domain API — no EF-bypass workaround was needed, and no signal for T073 is raised
/// here.
/// </para>
/// </remarks>
public sealed class InvitationRefusalTests : IClassFixture<ApiFactory>
{
    private readonly ApiFactory _factory;

    public InvitationRefusalTests(SqlServerFixture sqlServerFixture, ApiFactory factory)
    {
        _factory = factory;
        _factory.UseConnectionString(sqlServerFixture.ConnectionString);
    }

    /// <summary>
    /// An unknown token — one that was never issued/persisted at all — must yield 404, exactly
    /// like every other case in this file, so a caller cannot distinguish "never existed" from
    /// "existed but is no longer usable".
    /// </summary>
    [Fact]
    public async Task Post_AcceptUnknownToken_Returns404()
    {
        await _factory.InitializeDatabaseAsync();
        await _factory.SeedTwoTenantsAsync();

        using var client = CreateInviteeClient(Guid.NewGuid().ToString(), "nobody@example.com");

        var response = await client.PostAsync(
            $"/invitations/{Guid.NewGuid()}/accept",
            content: null,
            TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.NotFound);
    }

    /// <summary>
    /// A genuinely-persisted invitation whose expiry has already passed must yield 404, not a
    /// different code that would reveal the token once resolved to a real, time-expired
    /// invitation.
    /// </summary>
    [Fact]
    public async Task Post_AcceptExpiredToken_Returns404()
    {
        await _factory.InitializeDatabaseAsync();
        var seed = await _factory.SeedTwoTenantsAsync();

        const string invitedEmail = "expired-invitee@tenant-a.example.com";
        const string rawToken = "refusal-expired-token";
        await SeedExpiredInvitationAsync(seed.TenantA.TenantId, invitedEmail, rawToken);

        using var client = CreateInviteeClient(Guid.NewGuid().ToString(), invitedEmail);

        var response = await client.PostAsync(
            $"/invitations/{rawToken}/accept",
            content: null,
            TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.NotFound);
    }

    /// <summary>
    /// A genuinely-persisted invitation that was explicitly revoked before anyone accepted it
    /// must yield 404, indistinguishable from a token that never existed.
    /// </summary>
    [Fact]
    public async Task Post_AcceptRevokedToken_Returns404()
    {
        await _factory.InitializeDatabaseAsync();
        var seed = await _factory.SeedTwoTenantsAsync();

        const string invitedEmail = "revoked-invitee@tenant-a.example.com";
        const string rawToken = "refusal-revoked-token";
        await SeedRevokedInvitationAsync(seed.TenantA.TenantId, invitedEmail, rawToken);

        using var client = CreateInviteeClient(Guid.NewGuid().ToString(), invitedEmail);

        var response = await client.PostAsync(
            $"/invitations/{rawToken}/accept",
            content: null,
            TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.NotFound);
    }

    /// <summary>
    /// A genuinely-persisted invitation that has already been accepted once must refuse a second
    /// acceptance attempt with 404, not (for example) a 409 Conflict that would leak "this token
    /// was valid and used before".
    /// </summary>
    [Fact]
    public async Task Post_AcceptAlreadyAcceptedToken_Returns404()
    {
        await _factory.InitializeDatabaseAsync();
        var seed = await _factory.SeedTwoTenantsAsync();

        const string invitedEmail = "already-accepted-invitee@tenant-a.example.com";
        const string rawToken = "refusal-already-accepted-token";
        await SeedAcceptedInvitationAsync(seed.TenantA.TenantId, invitedEmail, rawToken);

        using var client = CreateInviteeClient(Guid.NewGuid().ToString(), invitedEmail);

        var response = await client.PostAsync(
            $"/invitations/{rawToken}/accept",
            content: null,
            TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.NotFound);
    }

    private HttpClient CreateInviteeClient(string entraObjectId, string invitedEmail)
    {
        var client = _factory.CreateClient();
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("TestScheme", "test");
        client.DefaultRequestHeaders.Add("X-Test-Oid", entraObjectId);
        client.DefaultRequestHeaders.Add("X-Test-Tid", Guid.NewGuid().ToString());
        client.DefaultRequestHeaders.Add("X-Test-Email", invitedEmail);
        return client;
    }

    /// <summary>
    /// Seeds a genuinely-persisted, already-expired <see cref="Invitation"/>. Local equivalent of
    /// <see cref="InviteAndManageMembersTests"/>'s (T063) <c>SeedExpiredInvitationAsync</c> helper,
    /// which is <c>private</c> to that class and therefore inaccessible from here.
    /// </summary>
    private async Task SeedExpiredInvitationAsync(TenantId tenantId, string invitedEmail, string rawToken)
    {
        using var scope = _factory.Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<TenancyDbContext>();

        db.CurrentTenantId = tenantId;
        var invitation = Invitation.Create(
            tenantId,
            new EmailAddress(invitedEmail),
            Role.Member,
            tokenHash: $"hash-of-{rawToken}",
            expiresAtUtc: DateTimeOffset.UtcNow.AddDays(-1));
        db.Invitations.Add(invitation);
        await db.SaveChangesAsync();
    }

    /// <summary>
    /// Seeds a genuinely-persisted <see cref="Invitation"/> and immediately revokes it via
    /// <see cref="Invitation.Revoke"/> — the domain entity already exposes a real revoke
    /// operation, so no EF-bypass or T073 signal is needed here.
    /// </summary>
    private async Task SeedRevokedInvitationAsync(TenantId tenantId, string invitedEmail, string rawToken)
    {
        using var scope = _factory.Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<TenancyDbContext>();

        db.CurrentTenantId = tenantId;
        var invitation = Invitation.Create(
            tenantId,
            new EmailAddress(invitedEmail),
            Role.Member,
            tokenHash: $"hash-of-{rawToken}",
            expiresAtUtc: DateTimeOffset.UtcNow.AddDays(7));
        invitation.Revoke();
        db.Invitations.Add(invitation);
        await db.SaveChangesAsync();
    }

    /// <summary>
    /// Seeds a genuinely-persisted <see cref="Invitation"/> and immediately accepts it via
    /// <see cref="Invitation.Accept"/>, using a fixed real-time <see cref="IClock"/> so acceptance
    /// unambiguously succeeds before the token is attempted a second time by the test itself.
    /// </summary>
    private async Task SeedAcceptedInvitationAsync(TenantId tenantId, string invitedEmail, string rawToken)
    {
        using var scope = _factory.Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<TenancyDbContext>();

        db.CurrentTenantId = tenantId;
        var invitation = Invitation.Create(
            tenantId,
            new EmailAddress(invitedEmail),
            Role.Member,
            tokenHash: $"hash-of-{rawToken}",
            expiresAtUtc: DateTimeOffset.UtcNow.AddDays(7));
        invitation.Accept(new SystemClock());
        db.Invitations.Add(invitation);
        await db.SaveChangesAsync();
    }

    private sealed class SystemClock : IClock
    {
        public DateTimeOffset UtcNow => DateTimeOffset.UtcNow;
    }
}
