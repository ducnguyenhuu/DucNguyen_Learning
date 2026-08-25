using AwesomeAssertions;
using Microsoft.Data.SqlClient;
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
}
