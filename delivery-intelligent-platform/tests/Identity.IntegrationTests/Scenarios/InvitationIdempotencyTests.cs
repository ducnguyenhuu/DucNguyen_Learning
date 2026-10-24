using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using ArchitectureTests.Support;
using AwesomeAssertions;
using Microsoft.Extensions.DependencyInjection;
using Identity.Domain.Abstractions;
using Identity.Domain.Memberships;
using Identity.Domain.Tenants;
using Identity.Domain.Users;
using Identity.Infrastructure.Persistence;
using Identity.IntegrationTests.Infrastructure;
using Xunit;

namespace Identity.IntegrationTests.Scenarios;

/// <summary>
/// Failing tests (T066) proving that FR-020's idempotency guarantee — already proven for
/// <c>POST /tenants</c> by <see cref="IdempotencyTests"/> (T050/T056/T058/T061) — also applies to
/// <c>POST /tenants/{tenantId}/invitations</c> once that endpoint is wired onto the same
/// <c>IdempotencyFilter</c> (T078). This file does not add a new mechanism; it re-proves the
/// already-correct filter behavior against a second, tenant-scoped endpoint.
/// </summary>
/// <remarks>
/// <b>What this file proves right now, and what it doesn't.</b> Same caveat as
/// <see cref="IdempotencyTests"/> and <see cref="InviteAndManageMembersTests"/>: neither
/// <c>POST /tenants/{tenantId}/invitations</c> (T078) nor its idempotency wiring exist yet, so
/// every request below hits a route absent from <c>Program.cs</c>'s route table and gets ASP.NET
/// Core's own "no matching endpoint" 404 — not any real idempotency behavior. These tests encode
/// the eventual-correct behavior per openapi.yaml/FR-020 so they go genuinely green once T078
/// lands.
/// </remarks>
public sealed class InvitationIdempotencyTests : IdentityIntegrationTestBase
{

    public InvitationIdempotencyTests(SqlServerFixture sqlServerFixture, ApiFactory factory)
        : base(sqlServerFixture, factory)
    {
    }

    /// <summary>
    /// Sending the exact same <c>POST /tenants/{tenantId}/invitations</c> request (same
    /// <c>Idempotency-Key</c>, same body) twice must return the same status code both times — a
    /// 201 replays as 201, never a 200 — with the second response's body identical to the first,
    /// with <c>Idempotency-Replayed: true</c> present only on the replay, and with exactly one
    /// invitation actually persisted, confirmed via <c>GET /tenants/{tenantId}/invitations</c>.
    /// </summary>
    [CoversRequirement("FR-020")]
    [Fact]
    public async Task Post_Invitations_ReplayedWithSameKeyAndBody_ReturnsSameStatusAndBodyVerbatim_AndOnlyOneInvitationExists()
    {
        await Factory.InitializeDatabaseAsync();
        var administrator = await SeedSoleAdministratorTenantAsync();

        using var client = CreateAuthenticatedClient(administrator);

        var idempotencyKey = Guid.CreateVersion7().ToString();
        const string invitedEmail = "invitee@sole-admin-tenant.example.com";

        var firstResponse = await SendPostInvitation(
            client, administrator.TenantId, idempotencyKey, invitedEmail, "Member");
        var firstBody = await firstResponse.Content.ReadAsStringAsync(TestContext.Current.CancellationToken);
        var firstReplayedHeader = GetIdempotencyReplayedHeaderValue(firstResponse);

        var secondResponse = await SendPostInvitation(
            client, administrator.TenantId, idempotencyKey, invitedEmail, "Member");
        var secondBody = await secondResponse.Content.ReadAsStringAsync(TestContext.Current.CancellationToken);

        secondResponse.StatusCode.Should().Be(firstResponse.StatusCode);
        secondResponse.StatusCode.Should().Be(HttpStatusCode.Created);
        secondBody.Should().Be(firstBody);

        firstReplayedHeader.Should().NotBe("true");
        GetIdempotencyReplayedHeaderValue(secondResponse).Should().Be("true");

        var listResponse = await client.GetAsync(
            $"/tenants/{administrator.TenantId.Value}/invitations",
            TestContext.Current.CancellationToken);
        listResponse.StatusCode.Should().Be(HttpStatusCode.OK);

        var listBody = await listResponse.Content.ReadAsStringAsync(TestContext.Current.CancellationToken);
        var occurrences = CountOccurrences(listBody, invitedEmail);
        occurrences.Should().Be(1);
    }

    /// <summary>
    /// Reusing the same <c>Idempotency-Key</c> against
    /// <c>POST /tenants/{tenantId}/invitations</c> with a materially different request body (a
    /// different invited email) must be rejected as key reuse with <c>422</c>, per the same
    /// mismatch-detection behavior already proven for <c>POST /tenants</c> by
    /// <see cref="IdempotencyTests.Post_Tenants_SameKeyDifferentBody_ReturnsUnprocessableEntity"/>.
    /// </summary>
    [CoversRequirement("FR-020")]
    [Fact]
    public async Task Post_Invitations_SameKeyDifferentBody_ReturnsUnprocessableEntity()
    {
        await Factory.InitializeDatabaseAsync();
        var administrator = await SeedSoleAdministratorTenantAsync();

        using var client = CreateAuthenticatedClient(administrator);

        var idempotencyKey = Guid.CreateVersion7().ToString();

        await SendPostInvitation(
            client, administrator.TenantId, idempotencyKey, "first-invitee@sole-admin-tenant.example.com", "Member");
        var secondResponse = await SendPostInvitation(
            client, administrator.TenantId, idempotencyKey, "second-invitee@sole-admin-tenant.example.com", "Member");

        secondResponse.StatusCode.Should().Be(HttpStatusCode.UnprocessableEntity);
    }

    private static async Task<HttpResponseMessage> SendPostInvitation(
        HttpClient client, TenantId tenantId, string idempotencyKey, string email, string role)
    {
        using var request = new HttpRequestMessage(
            HttpMethod.Post, $"/tenants/{tenantId.Value}/invitations")
        {
            Content = JsonContent.Create(new { email, role }),
        };
        request.Headers.Add("Idempotency-Key", idempotencyKey);

        return await client.SendAsync(request, TestContext.Current.CancellationToken);
    }

    private static string? GetIdempotencyReplayedHeaderValue(HttpResponseMessage response) =>
        response.Headers.TryGetValues("Idempotency-Replayed", out var values) ? values.FirstOrDefault() : null;

    private static int CountOccurrences(string haystack, string needle)
    {
        var count = 0;
        var index = 0;
        while ((index = haystack.IndexOf(needle, index, StringComparison.Ordinal)) != -1)
        {
            count++;
            index += needle.Length;
        }

        return count;
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
    /// Seeds a single tenant with exactly one active <see cref="Role.Administrator"/> member —
    /// this route is tenant-scoped and requires an authenticated administrator caller, unlike
    /// <c>POST /tenants</c>'s ADR-017 unscoped-exception pattern used by
    /// <see cref="IdempotencyTests"/>. Mirrors
    /// <see cref="InviteAndManageMembersTests.SeedSoleAdministratorTenantAsync"/>'s shape.
    /// </summary>
    private async Task<SeededTenant> SeedSoleAdministratorTenantAsync()
    {
        using var scope = Factory.Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<IdentityDbContext>();

        var tenant = Tenant.Create("Sole Admin Invitation Tenant");
        var admin = User.Create(
            entraTenantId: Guid.CreateVersion7(),
            entraObjectId: Guid.CreateVersion7(),
            email: new EmailAddress("sole-admin@sole-admin-invitation-tenant.example.com"));

        db.Tenants.Add(tenant);
        db.Users.Add(admin);
        await db.SaveChangesAsync();

        db.CurrentTenantId = tenant.Id;
        var membership = Membership.Create(tenant.Id, admin.Id, Role.Administrator);
        db.Memberships.Add(membership);
        await db.SaveChangesAsync();

        return new SeededTenant(tenant.Id, admin.Id, membership.Id, admin.EntraTenantId, admin.EntraObjectId);
    }
}
