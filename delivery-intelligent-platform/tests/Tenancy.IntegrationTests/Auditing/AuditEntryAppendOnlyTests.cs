using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using AwesomeAssertions;
using Microsoft.Data.SqlClient;
using Microsoft.Extensions.DependencyInjection;
using Tenancy.Api.ETags;
using Tenancy.Domain.Abstractions;
using Tenancy.Domain.Memberships;
using Tenancy.Domain.Tenants;
using Tenancy.Domain.Users;
using Tenancy.Infrastructure.Persistence;
using Tenancy.IntegrationTests.Infrastructure;
using Xunit;

namespace Tenancy.IntegrationTests.Auditing;

/// <summary>
/// Proves the append-only guarantee on <c>AuditEntries</c> (FR-011) structurally, against the
/// real SQL Server container, by issuing direct <c>UPDATE</c>/<c>DELETE</c> statements via plain
/// ADO.NET — bypassing the application entirely (no <c>TenancyDbContext</c>/EF Core involved) —
/// and asserting the database itself rejects both via <c>TR_AuditEntries_PreventModification</c>
/// (added in the <c>AddAuditEntries</c> migration).
/// </summary>
/// <remarks>
/// <c>AuditEntries</c> is excluded from Respawn's per-test reset (see <see cref="ApiFactory"/>'s
/// remarks — the trigger rejects Respawn's own DELETE too), so rows from other tests may already
/// be present when this test runs. This test therefore inserts its own row carrying a freshly
/// generated <see cref="System.Guid"/> in <c>ResourceId</c> and only ever targets that row via a
/// <c>WHERE ResourceId = @resourceId</c> clause — it never assumes the table is empty and never
/// asserts a total row count.
/// </remarks>
public sealed class AuditEntryAppendOnlyTests : TenancyIntegrationTestBase
{
    private readonly string _connectionString;

    public AuditEntryAppendOnlyTests(SqlServerFixture sqlServerFixture, ApiFactory factory)
        : base(sqlServerFixture, factory)
    {
        _connectionString = sqlServerFixture.ConnectionString;
    }

    [Fact]
    public async Task DirectUpdateAndDelete_AgainstAuditEntries_AreBothRejectedByTheDatabase()
    {
        await Factory.InitializeDatabaseAsync();

        var resourceId = Guid.NewGuid().ToString();
        var cancellationToken = TestContext.Current.CancellationToken;

        await using var connection = new SqlConnection(_connectionString);
        await connection.OpenAsync(cancellationToken);

        const string originalAction = "OriginalAction";

        await using (var insert = connection.CreateCommand())
        {
            insert.CommandText = """
                INSERT INTO AuditEntries (Id, TenantId, ActorUserId, Action, ResourceType, ResourceId, OccurredAtUtc)
                VALUES (@id, NULL, NULL, @action, @resourceType, @resourceId, @occurredAtUtc)
                """;
            insert.Parameters.AddWithValue("@id", Guid.NewGuid());
            insert.Parameters.AddWithValue("@action", originalAction);
            insert.Parameters.AddWithValue("@resourceType", "TestResource");
            insert.Parameters.AddWithValue("@resourceId", resourceId);
            insert.Parameters.AddWithValue("@occurredAtUtc", DateTimeOffset.UtcNow);
            await insert.ExecuteNonQueryAsync(cancellationToken);
        }

        await using (var update = connection.CreateCommand())
        {
            update.CommandText = "UPDATE AuditEntries SET Action = @newAction WHERE ResourceId = @resourceId";
            update.Parameters.AddWithValue("@newAction", "TamperedAction");
            update.Parameters.AddWithValue("@resourceId", resourceId);

            var act = async () => await update.ExecuteNonQueryAsync(cancellationToken);

            await act.Should().ThrowAsync<SqlException>();
        }

        await using (var delete = connection.CreateCommand())
        {
            delete.CommandText = "DELETE FROM AuditEntries WHERE ResourceId = @resourceId";
            delete.Parameters.AddWithValue("@resourceId", resourceId);

            var act = async () => await delete.ExecuteNonQueryAsync(cancellationToken);

            await act.Should().ThrowAsync<SqlException>();
        }

        await using (var select = connection.CreateCommand())
        {
            select.CommandText = "SELECT Action FROM AuditEntries WHERE ResourceId = @resourceId";
            select.Parameters.AddWithValue("@resourceId", resourceId);

            var result = await select.ExecuteScalarAsync(cancellationToken);

            result.Should().Be(originalAction);
        }
    }

    /// <summary>
    /// Removing a membership through the real endpoint produces exactly one
    /// <see cref="Tenancy.Domain.Auditing.AuditEntry"/> row describing that removal, persisted
    /// atomically with the removal itself.
    /// </summary>
    [Fact]
    public async Task Delete_ActiveMember_ProducesExactlyOneMatchingAuditEntry()
    {
        await Factory.InitializeDatabaseAsync();
        var seed = await SeedAdministratorAndMemberAsync();
        var cancellationToken = TestContext.Current.CancellationToken;

        using var adminClient = CreateAuthenticatedClient(seed.Administrator);
        var ifMatch = await GetMembershipIfMatchAsync(seed.Administrator.TenantId, seed.Member.MembershipId);
        adminClient.DefaultRequestHeaders.Add("If-Match", ifMatch);

        var response = await adminClient.DeleteAsync(
            $"/tenants/{seed.Administrator.TenantId.Value}/members/{seed.Member.UserId.Value}",
            cancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.NoContent);

        await using var connection = new SqlConnection(_connectionString);
        await connection.OpenAsync(cancellationToken);

        await using var select = connection.CreateCommand();
        select.CommandText = """
            SELECT COUNT(*)
            FROM AuditEntries
            WHERE TenantId = @tenantId
              AND ActorUserId = @actorUserId
              AND ResourceId = @resourceId
              AND Action LIKE 'membership.removed%'
            """;
        select.Parameters.AddWithValue("@tenantId", seed.Administrator.TenantId.Value);
        select.Parameters.AddWithValue("@actorUserId", seed.Administrator.UserId.Value);
        select.Parameters.AddWithValue("@resourceId", seed.Member.UserId.Value.ToString());

        var matchingRowCount = (int)(await select.ExecuteScalarAsync(cancellationToken))!;

        matchingRowCount.Should().Be(1,
            "removing a membership must produce exactly one matching audit entry");
    }

    /// <summary>
    /// The atomicity half of this coverage: an attempt to remove a tenant's <em>last</em> administrator is refused
    /// (409 Conflict, the last-administrator invariant in
    /// <c>RemoveMember.cs</c>) — neither the membership nor an audit entry for the attempt should
    /// exist afterward, proving the removal and its audit entry rise and fall together without
    /// needing an artificially injected failure.
    /// </summary>
    [Fact]
    public async Task Delete_SoleAdministrator_IsRefused_AndProducesNoAuditEntry()
    {
        await Factory.InitializeDatabaseAsync();
        var seed = await SeedSoleAdministratorTenantAsync();
        var cancellationToken = TestContext.Current.CancellationToken;

        using var client = CreateAuthenticatedClient(seed.EntraTenantId, seed.EntraObjectId);
        var ifMatch = await GetMembershipIfMatchAsync(seed.TenantId, seed.MembershipId);
        client.DefaultRequestHeaders.Add("If-Match", ifMatch);

        var response = await client.DeleteAsync(
            $"/tenants/{seed.TenantId.Value}/members/{seed.UserId.Value}",
            cancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.Conflict);

        await using var connection = new SqlConnection(_connectionString);
        await connection.OpenAsync(cancellationToken);

        await using var select = connection.CreateCommand();
        select.CommandText = """
            SELECT COUNT(*)
            FROM AuditEntries
            WHERE TenantId = @tenantId
              AND ResourceId = @resourceId
              AND Action LIKE 'membership.removed%'
            """;
        select.Parameters.AddWithValue("@tenantId", seed.TenantId.Value);
        select.Parameters.AddWithValue("@resourceId", seed.UserId.Value.ToString());

        var matchingRowCount = (int)(await select.ExecuteScalarAsync(cancellationToken))!;

        matchingRowCount.Should().Be(0,
            "a refused removal (409, last-administrator invariant) must not leave behind an " +
            "audit entry for a removal that never happened");
    }

    /// <summary>
    /// An authorization refusal that spec 001 FR-025 requires to be logged (a
    /// non-administrator attempting an administrator-only action — here, inviting a member) must
    /// also produce a matching <see cref="Tenancy.Domain.Auditing.AuditEntry"/> row.
    /// </summary>
    [Fact]
    public async Task Post_Invitation_AsNonAdministrator_IsRefused_AndProducesMatchingAuditEntry()
    {
        await Factory.InitializeDatabaseAsync();
        var seed = await SeedAdministratorAndMemberAsync();
        var cancellationToken = TestContext.Current.CancellationToken;

        using var memberClient = CreateAuthenticatedClient(seed.Member);
        memberClient.DefaultRequestHeaders.Add("Idempotency-Key", Guid.NewGuid().ToString());

        var response = await memberClient.PostAsJsonAsync(
            $"/tenants/{seed.Administrator.TenantId.Value}/invitations",
            new { email = "refused-invitee@admin-and-member-tenant.example.com", role = "Member" },
            cancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.Forbidden);

        await using var connection = new SqlConnection(_connectionString);
        await connection.OpenAsync(cancellationToken);

        await using var select = connection.CreateCommand();
        select.CommandText = """
            SELECT COUNT(*)
            FROM AuditEntries
            WHERE TenantId = @tenantId
              AND ActorUserId = @actorUserId
              AND Action LIKE 'authorization.refused%'
            """;
        select.Parameters.AddWithValue("@tenantId", seed.Administrator.TenantId.Value);
        select.Parameters.AddWithValue("@actorUserId", seed.Member.UserId.Value);

        var matchingRowCount = (int)(await select.ExecuteScalarAsync(cancellationToken))!;

        matchingRowCount.Should().BeGreaterThanOrEqualTo(1,
            "an authorization refusal per spec 001 FR-025 must produce a matching audit entry");
    }

    private HttpClient CreateAuthenticatedClient(SeededTenant seededTenant) =>
        CreateAuthenticatedClient(seededTenant.EntraTenantId, seededTenant.EntraObjectId);

    private HttpClient CreateAuthenticatedClient(Guid entraTenantId, Guid entraObjectId)
    {
        var client = Factory.CreateClient();
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("TestScheme", "test");
        client.DefaultRequestHeaders.Add("X-Test-Oid", entraObjectId.ToString());
        client.DefaultRequestHeaders.Add("X-Test-Tid", entraTenantId.ToString());
        return client;
    }

    /// <summary>
    /// Builds a valid <c>If-Match</c> value directly from the membership's current, persisted
    /// <c>RowVersion</c> — mirrors the established pattern in
    /// <c>RolePermissionMatrixTests</c>/<c>InviteAndManageMembersTests</c>, since
    /// <c>DELETE /tenants/{tenantId}/members/{userId}</c> requires a genuine If-Match
    /// precondition (contracts/openapi.yaml, FR-021).
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
    /// Seeds a single tenant with exactly one active <see cref="Role.Administrator"/> and one
    /// active <see cref="Role.Member"/> — local equivalent of the same-shaped helper in
    /// <c>InviteAndManageMembersTests</c>/<c>RolePermissionMatrixTests</c>, both <c>private</c> to
    /// their own classes and therefore inaccessible from here.
    /// </summary>
    private async Task<AdministratorAndMemberSeed> SeedAdministratorAndMemberAsync()
    {
        using var scope = Factory.Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<TenancyDbContext>();

        var tenant = Tenant.Create("Audit Admin And Member Tenant");
        var admin = User.Create(
            entraTenantId: Guid.CreateVersion7(),
            entraObjectId: Guid.CreateVersion7(),
            email: new EmailAddress("admin@audit-admin-and-member-tenant.example.com"));
        var member = User.Create(
            entraTenantId: Guid.CreateVersion7(),
            entraObjectId: Guid.CreateVersion7(),
            email: new EmailAddress("member@audit-admin-and-member-tenant.example.com"));

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
    /// needed to attempt removing the last administrator, mirroring the same-shaped helper in
    /// <c>InviteAndManageMembersTests</c>.
    /// </summary>
    private async Task<SeededTenant> SeedSoleAdministratorTenantAsync()
    {
        using var scope = Factory.Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<TenancyDbContext>();

        var tenant = Tenant.Create("Audit Sole Admin Tenant");
        var admin = User.Create(
            entraTenantId: Guid.CreateVersion7(),
            entraObjectId: Guid.CreateVersion7(),
            email: new EmailAddress("sole-admin@audit-sole-admin-tenant.example.com"));

        db.Tenants.Add(tenant);
        db.Users.Add(admin);
        await db.SaveChangesAsync();

        db.CurrentTenantId = tenant.Id;
        var membership = Membership.Create(tenant.Id, admin.Id, Role.Administrator);
        db.Memberships.Add(membership);
        await db.SaveChangesAsync();

        return new SeededTenant(tenant.Id, admin.Id, membership.Id, admin.EntraTenantId, admin.EntraObjectId);
    }

    private sealed record AdministratorAndMemberSeed(SeededTenant Administrator, SeededTenant Member);
}
