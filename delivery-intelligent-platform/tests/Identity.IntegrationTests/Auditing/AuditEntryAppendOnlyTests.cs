using System.Net;
using System.Net.Http.Json;
using AwesomeAssertions;
using Microsoft.Data.SqlClient;
using Identity.Domain.Abstractions;
using Identity.IntegrationTests.Infrastructure;
using Xunit;

namespace Identity.IntegrationTests.Auditing;

/// <summary>
/// Proves the append-only guarantee on <c>AuditEntries</c> (FR-011) structurally, against the
/// real SQL Server container, by issuing direct <c>UPDATE</c>/<c>DELETE</c> statements via plain
/// ADO.NET — bypassing the application entirely (no <c>IdentityDbContext</c>/EF Core involved) —
/// and asserting the database itself rejects both via <c>TR_AuditEntries_PreventModification</c>
/// (created by the <c>InitialIdentity</c> migration).
/// </summary>
/// <remarks>
/// <c>AuditEntries</c> is excluded from Respawn's per-test reset (see <see cref="ApiFactory"/>'s
/// remarks — the trigger rejects Respawn's own DELETE too), so rows from other tests may already
/// be present when this test runs. This test therefore inserts its own row carrying a freshly
/// generated <see cref="System.Guid"/> in <c>ResourceId</c> and only ever targets that row via a
/// <c>WHERE ResourceId = @resourceId</c> clause — it never assumes the table is empty and never
/// asserts a total row count.
/// </remarks>
public sealed class AuditEntryAppendOnlyTests : IdentityIntegrationTestBase
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

        var resourceId = Guid.NewGuid().ToString();
        var cancellationToken = TestContext.Current.CancellationToken;

        await using var connection = new SqlConnection(_connectionString);
        await connection.OpenAsync(cancellationToken);

        const string originalAction = "OriginalAction";

        await using (var insert = connection.CreateCommand())
        {
            insert.CommandText = """
                INSERT INTO AuditEntries (Id, ActorUserId, Action, ResourceType, ResourceId, OccurredAtUtc)
                VALUES (@id, NULL, @action, @resourceType, @resourceId, @occurredAtUtc)
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
    /// <see cref="Identity.Domain.Auditing.AuditEntry"/> row describing that removal, persisted
    /// atomically with the removal itself.
    /// </summary>
    [Fact]
    public async Task Delete_ActiveMember_ProducesExactlyOneMatchingAuditEntry()
    {
        var seed = await SeedAdministratorAndMemberAsync();
        var cancellationToken = TestContext.Current.CancellationToken;

        using var adminClient = Factory.CreateClientFor(seed.Administrator);
        var ifMatch = await Factory.GetMembershipIfMatchAsync(seed.Member.MembershipId);
        adminClient.DefaultRequestHeaders.Add("If-Match", ifMatch);

        var response = await adminClient.DeleteAsync(
            $"/members/{seed.Member.UserId.Value}",
            cancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.NoContent);

        await using var connection = new SqlConnection(_connectionString);
        await connection.OpenAsync(cancellationToken);

        await using var select = connection.CreateCommand();
        select.CommandText = """
            SELECT COUNT(*)
            FROM AuditEntries
            WHERE ActorUserId = @actorUserId
              AND ResourceId = @resourceId
              AND Action LIKE 'membership.removed%'
            """;
        select.Parameters.AddWithValue("@actorUserId", seed.Administrator.UserId.Value);
        select.Parameters.AddWithValue("@resourceId", seed.Member.UserId.Value.ToString());

        var matchingRowCount = (int)(await select.ExecuteScalarAsync(cancellationToken))!;

        matchingRowCount.Should().Be(1,
            "removing a membership must produce exactly one matching audit entry");
    }

    /// <summary>
    /// The atomicity half of this coverage: an attempt to remove the organization's <em>last</em> administrator is refused
    /// (409 Conflict, the last-administrator invariant in
    /// <c>RemoveMember.cs</c>) — neither the membership nor an audit entry for the attempt should
    /// exist afterward, proving the removal and its audit entry rise and fall together without
    /// needing an artificially injected failure.
    /// </summary>
    [Fact]
    public async Task Delete_SoleAdministrator_IsRefused_AndProducesNoAuditEntry()
    {
        var seed = await Factory.SeedMemberAsync(Role.Administrator);
        var cancellationToken = TestContext.Current.CancellationToken;

        using var client = Factory.CreateClientFor(seed);
        var ifMatch = await Factory.GetMembershipIfMatchAsync(seed.MembershipId);
        client.DefaultRequestHeaders.Add("If-Match", ifMatch);

        var response = await client.DeleteAsync(
            $"/members/{seed.UserId.Value}",
            cancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.Conflict);

        await using var connection = new SqlConnection(_connectionString);
        await connection.OpenAsync(cancellationToken);

        await using var select = connection.CreateCommand();
        select.CommandText = """
            SELECT COUNT(*)
            FROM AuditEntries
            WHERE ResourceId = @resourceId
              AND Action LIKE 'membership.removed%'
            """;
        select.Parameters.AddWithValue("@resourceId", seed.UserId.Value.ToString());

        var matchingRowCount = (int)(await select.ExecuteScalarAsync(cancellationToken))!;

        matchingRowCount.Should().Be(0,
            "a refused removal (409, last-administrator invariant) must not leave behind an " +
            "audit entry for a removal that never happened");
    }

    /// <summary>
    /// An authorization refusal that spec 001 FR-025 requires to be logged (a
    /// non-administrator attempting an administrator-only action — here, inviting a member) must
    /// also produce a matching <see cref="Identity.Domain.Auditing.AuditEntry"/> row.
    /// </summary>
    [Fact]
    public async Task Post_Invitation_AsNonAdministrator_IsRefused_AndProducesMatchingAuditEntry()
    {
        var seed = await SeedAdministratorAndMemberAsync();
        var cancellationToken = TestContext.Current.CancellationToken;

        using var memberClient = Factory.CreateClientFor(seed.Member);
        memberClient.DefaultRequestHeaders.Add("Idempotency-Key", Guid.NewGuid().ToString());

        var response = await memberClient.PostAsJsonAsync(
            "/invitations",
            new { email = "refused-invitee@example.com", role = "Member" },
            cancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.Forbidden);

        await using var connection = new SqlConnection(_connectionString);
        await connection.OpenAsync(cancellationToken);

        await using var select = connection.CreateCommand();
        select.CommandText = """
            SELECT COUNT(*)
            FROM AuditEntries
            WHERE ActorUserId = @actorUserId
              AND Action LIKE 'authorization.refused%'
            """;
        select.Parameters.AddWithValue("@actorUserId", seed.Member.UserId.Value);

        var matchingRowCount = (int)(await select.ExecuteScalarAsync(cancellationToken))!;

        matchingRowCount.Should().BeGreaterThanOrEqualTo(1,
            "an authorization refusal per spec 001 FR-025 must produce a matching audit entry");
    }

    private async Task<AdministratorAndMemberSeed> SeedAdministratorAndMemberAsync() =>
        new(await Factory.SeedMemberAsync(Role.Administrator), await Factory.SeedMemberAsync(Role.Member));

    private sealed record AdministratorAndMemberSeed(SeededMember Administrator, SeededMember Member);
}
