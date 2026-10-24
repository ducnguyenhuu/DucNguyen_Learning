using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Identity.Infrastructure.Migrations;

/// <inheritdoc />
public partial class AddAuditEntries : Migration
{
    /// <inheritdoc />
    protected override void Up(MigrationBuilder migrationBuilder)
    {
        migrationBuilder.CreateTable(
            name: "AuditEntries",
            columns: table => new
            {
                Id = table.Column<Guid>(type: "uniqueidentifier", nullable: false),
                TenantId = table.Column<Guid>(type: "uniqueidentifier", nullable: true),
                ActorUserId = table.Column<Guid>(type: "uniqueidentifier", nullable: true),
                Action = table.Column<string>(type: "nvarchar(max)", nullable: false),
                ResourceType = table.Column<string>(type: "nvarchar(max)", nullable: false),
                ResourceId = table.Column<string>(type: "nvarchar(max)", nullable: false),
                OccurredAtUtc = table.Column<DateTimeOffset>(type: "datetimeoffset", nullable: false)
            },
            constraints: table =>
            {
                table.PrimaryKey("PK_AuditEntries", x => x.Id);
            });

        // FR-011: the append-only guarantee must be structural, enforced by the database
        // itself, not an application-code convention. This trigger unconditionally rejects
        // any UPDATE or DELETE against AuditEntries, regardless of which credentials or code
        // path issues the statement.
        migrationBuilder.Sql(
            """
            CREATE TRIGGER TR_AuditEntries_PreventModification
            ON AuditEntries
            AFTER UPDATE, DELETE
            AS
            BEGIN
                RAISERROR('AuditEntries is append-only; UPDATE and DELETE are not permitted.', 16, 1);
                ROLLBACK TRANSACTION;
            END
            """);
    }

    /// <inheritdoc />
    protected override void Down(MigrationBuilder migrationBuilder)
    {
        migrationBuilder.Sql("DROP TRIGGER TR_AuditEntries_PreventModification;");

        migrationBuilder.DropTable(
            name: "AuditEntries");
    }
}
