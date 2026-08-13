using System.Net;
using System.Net.Http.Headers;
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
/// FR-025 coverage (T089 gap closure): proves the *substantive* half of FR-025 — that a tenant
/// mutation and a membership-resolution refusal actually produce a structured, diagnosable log
/// entry — which <see cref="LogHygieneTests"/> explicitly disclaims covering (it only proves
/// incidental framework logging never leaks a secret/token; it says nothing about whether the
/// business-event logging FR-025 requires actually fires).
/// </summary>
/// <remarks>
/// Uses the same <see cref="ApiFactory.CapturedLogMessages"/> / <see cref="ApiFactory.ClearCapturedLogs"/>
/// capture mechanism <see cref="LogHygieneTests"/> already relies on (T053), so no new
/// test-infrastructure is introduced here.
/// </remarks>
public sealed class LoggingCoverageTests : TenancyIntegrationTestBase
{
    public LoggingCoverageTests(SqlServerFixture sqlServerFixture, ApiFactory factory)
        : base(sqlServerFixture, factory)
    {
    }

    /// <summary>
    /// FR-025's "tenant mutation" category: creating a tenant must produce a structured log entry
    /// identifying which tenant was created and by which user (see
    /// <c>CreateTenant.ExecuteAsync</c>'s <c>_logger.LogInformation("Tenant {TenantId} created by
    /// user {UserId}", ...)</c> call), and must not log anything beyond the two ids (no display
    /// name, no email, no other personal data).
    /// </summary>
    [Fact]
    public async Task Post_Tenants_LogsTenantCreationWithTenantAndUserId_AndNoDisplayName()
    {
        await Factory.InitializeDatabaseAsync();

        using var client = Factory.CreateClient();
        var callerObjectId = Guid.NewGuid();
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("TestScheme", "test");
        client.DefaultRequestHeaders.Add("X-Test-Oid", callerObjectId.ToString());
        client.DefaultRequestHeaders.Add("X-Test-Tid", Guid.NewGuid().ToString());
        client.DefaultRequestHeaders.Add("Idempotency-Key", Guid.NewGuid().ToString());

        Factory.ClearCapturedLogs();

        const string displayName = "LoggingCoverage-T089-Tenant";
        var response = await client.PostAsync(
            "/tenants",
            System.Net.Http.Json.JsonContent.Create(new { displayName }),
            TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.Created);

        var body = await response.Content.ReadAsStringAsync(TestContext.Current.CancellationToken);
        var createdTenantId = System.Text.Json.JsonDocument.Parse(body).RootElement
            .GetProperty("id").GetString();
        createdTenantId.Should().NotBeNullOrWhiteSpace();

        var capturedLogs = Factory.CapturedLogMessages;

        capturedLogs.Should().Contain(
            message => message.Contains("created by user", StringComparison.Ordinal)
                && message.Contains(createdTenantId!, StringComparison.OrdinalIgnoreCase),
            "FR-025 requires tenant creation to be logged with enough structured detail to " +
            "diagnose it — at minimum the new tenant's id.");

        capturedLogs.Should().NotContain(
            message => message.Contains(displayName, StringComparison.Ordinal),
            "FR-025 forbids logging unnecessary personal/business data — the display name is " +
            "not required to diagnose a creation event and must not appear in the log line.");
    }

    /// <summary>
    /// FR-025's "authorisation refusal" category, at the tenant-context-resolution layer:
    /// a caller who is not a member of the requested tenant must produce a structured log entry
    /// documenting *why* resolution failed (see
    /// <c>TenantContextResolutionMiddleware.NotMember</c>'s <c>_logger.LogInformation("Membership
    /// resolution failed for candidate tenant {CandidateTenantId}: {Reason}", ...)</c> call) —
    /// server-side, even though the HTTP response itself must stay indistinguishable from a
    /// nonexistent tenant per FR-009/ADR-017.
    /// </summary>
    [Fact]
    public async Task Get_TenantById_ForOtherTenant_LogsMembershipResolutionFailure()
    {
        await Factory.InitializeDatabaseAsync();
        var seed = await Factory.SeedTwoTenantsAsync();

        using var client = Factory.CreateClient();
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("TestScheme", "test");
        client.DefaultRequestHeaders.Add("X-Test-Oid", seed.TenantA.EntraObjectId.ToString());
        client.DefaultRequestHeaders.Add("X-Test-Tid", seed.TenantA.EntraTenantId.ToString());

        Factory.ClearCapturedLogs();

        var response = await client.GetAsync(
            $"/tenants/{seed.TenantB.TenantId.Value}",
            TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.NotFound);

        var capturedLogs = Factory.CapturedLogMessages;

        capturedLogs.Should().Contain(
            message => message.Contains("Membership resolution failed", StringComparison.Ordinal)
                && message.Contains(seed.TenantB.TenantId.Value.ToString(), StringComparison.OrdinalIgnoreCase),
            "FR-025 requires authorisation refusals to be logged server-side with enough detail " +
            "to diagnose them, even though the HTTP response itself must stay indistinguishable " +
            "from a nonexistent tenant (FR-009).");
    }

    /// <summary>
    /// FR-025's "membership change" category: removing an active member must produce a
    /// structured log entry (see <c>RemoveMember.ExecuteAsync</c>'s logging call), scoped by
    /// tenant/membership id only — no email address, which is exactly the kind of unnecessary
    /// personal data FR-025 forbids.
    /// </summary>
    [Fact]
    public async Task Delete_Member_LogsMembershipChange_ByUserIdOnly_NoEmail()
    {
        await Factory.InitializeDatabaseAsync();
        var seed = await SeedAdministratorAndMemberAsync();

        using var adminClient = Factory.CreateClient();
        adminClient.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("TestScheme", "test");
        adminClient.DefaultRequestHeaders.Add("X-Test-Oid", seed.Administrator.EntraObjectId.ToString());
        adminClient.DefaultRequestHeaders.Add("X-Test-Tid", seed.Administrator.EntraTenantId.ToString());

        var ifMatch = await GetMembershipIfMatchAsync(seed.Administrator.TenantId, seed.Member.MembershipId);
        adminClient.DefaultRequestHeaders.Add("If-Match", ifMatch);

        Factory.ClearCapturedLogs();

        var deleteResponse = await adminClient.DeleteAsync(
            $"/tenants/{seed.Administrator.TenantId.Value}/members/{seed.Member.UserId.Value}",
            TestContext.Current.CancellationToken);

        deleteResponse.StatusCode.Should().Be(HttpStatusCode.NoContent);

        var capturedLogs = Factory.CapturedLogMessages;

        capturedLogs.Should().Contain(
            message => message.Contains(seed.Member.UserId.Value.ToString(), StringComparison.OrdinalIgnoreCase),
            "FR-025 requires membership changes (here, removal) to be logged with enough " +
            "structured detail to diagnose them — at minimum the removed member's user id.");

        capturedLogs.Should().NotContain(
            message => message.Contains("member@admin-and-member-tenant.example.com", StringComparison.OrdinalIgnoreCase),
            "FR-025 forbids logging unnecessary personal data — the removed member's email " +
            "address is not required to diagnose a removal event and must not appear in any " +
            "log line.");
    }

    private async Task<string> GetMembershipIfMatchAsync(TenantId tenantId, MembershipId membershipId)
    {
        using var scope = Factory.Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<TenancyDbContext>();
        db.CurrentTenantId = tenantId;
        var membership = await db.Memberships.FindAsync(
            [membershipId], TestContext.Current.CancellationToken);
        return RowVersionETag.ToETag(membership!.RowVersion);
    }

    private async Task<AdministratorAndMemberSeed> SeedAdministratorAndMemberAsync()
    {
        using var scope = Factory.Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<TenancyDbContext>();

        var tenant = Tenant.Create("LoggingCoverage Admin And Member Tenant");
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

    private sealed record AdministratorAndMemberSeed(SeededTenant Administrator, SeededTenant Member);
}
