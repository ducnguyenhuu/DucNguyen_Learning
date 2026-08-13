using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Tenancy.Infrastructure.Migrations;

/// <inheritdoc />
public partial class IdempotencyRecordSentinelKey : Migration
{
    /// <inheritdoc />
    protected override void Up(MigrationBuilder migrationBuilder)
    {
        migrationBuilder.DropPrimaryKey(
            name: "PK_IdempotencyRecords",
            table: "IdempotencyRecords");

        migrationBuilder.AddPrimaryKey(
            name: "PK_IdempotencyRecords",
            table: "IdempotencyRecords",
            columns: new[] { "TenantId", "CreatedByUserId", "Endpoint", "Key" });
    }

    /// <inheritdoc />
    protected override void Down(MigrationBuilder migrationBuilder)
    {
        migrationBuilder.DropPrimaryKey(
            name: "PK_IdempotencyRecords",
            table: "IdempotencyRecords");

        migrationBuilder.AddPrimaryKey(
            name: "PK_IdempotencyRecords",
            table: "IdempotencyRecords",
            columns: new[] { "TenantId", "Endpoint", "Key" });
    }
}
