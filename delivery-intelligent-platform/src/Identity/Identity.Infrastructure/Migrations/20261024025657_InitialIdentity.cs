using System;

using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Identity.Infrastructure.Migrations;

/// <inheritdoc />
public partial class InitialIdentity : Migration
{
    /// <inheritdoc />
    protected override void Up(MigrationBuilder migrationBuilder)
    {
        migrationBuilder.CreateTable(
            name: "AuditEntries",
            columns: table => new
            {
                Id = table.Column<Guid>(type: "uniqueidentifier", nullable: false),
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
        // path issues the statement. Carried over verbatim from the S4 AddAuditEntries
        // migration, which this single initial migration replaces (ADR-025).
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

        migrationBuilder.CreateTable(
            name: "IdempotencyRecords",
            columns: table => new
            {
                Endpoint = table.Column<string>(type: "nvarchar(256)", maxLength: 256, nullable: false),
                Key = table.Column<string>(type: "nvarchar(256)", maxLength: 256, nullable: false),
                CreatedByUserId = table.Column<Guid>(type: "uniqueidentifier", nullable: false),
                RequestHash = table.Column<byte[]>(type: "varbinary(32)", maxLength: 32, nullable: false),
                Status = table.Column<byte>(type: "tinyint", nullable: false),
                StatusCode = table.Column<int>(type: "int", nullable: true),
                ResponseBody = table.Column<string>(type: "nvarchar(max)", nullable: true),
                ResourceLocation = table.Column<string>(type: "nvarchar(max)", nullable: true),
                CreatedAtUtc = table.Column<DateTimeOffset>(type: "datetimeoffset", nullable: false),
                ExpiresAtUtc = table.Column<DateTimeOffset>(type: "datetimeoffset", nullable: false)
            },
            constraints: table =>
            {
                table.PrimaryKey("PK_IdempotencyRecords", x => new { x.CreatedByUserId, x.Endpoint, x.Key });
            });

        migrationBuilder.CreateTable(
            name: "Invitations",
            columns: table => new
            {
                Id = table.Column<Guid>(type: "uniqueidentifier", nullable: false),
                Email = table.Column<string>(type: "nvarchar(320)", maxLength: 320, nullable: false),
                Role = table.Column<string>(type: "nvarchar(max)", nullable: false),
                TokenHash = table.Column<string>(type: "nvarchar(64)", maxLength: 64, nullable: false),
                Status = table.Column<string>(type: "nvarchar(max)", nullable: false),
                ExpiresAtUtc = table.Column<DateTimeOffset>(type: "datetimeoffset", nullable: false),
                RowVersion = table.Column<byte[]>(type: "rowversion", rowVersion: true, nullable: false)
            },
            constraints: table =>
            {
                table.PrimaryKey("PK_Invitations", x => x.Id);
            });

        migrationBuilder.CreateTable(
            name: "Memberships",
            columns: table => new
            {
                Id = table.Column<Guid>(type: "uniqueidentifier", nullable: false),
                UserId = table.Column<Guid>(type: "uniqueidentifier", nullable: false),
                Role = table.Column<string>(type: "nvarchar(max)", nullable: false),
                Status = table.Column<string>(type: "nvarchar(450)", nullable: false),
                RemovedAtUtc = table.Column<DateTimeOffset>(type: "datetimeoffset", nullable: true),
                RowVersion = table.Column<byte[]>(type: "rowversion", rowVersion: true, nullable: false)
            },
            constraints: table =>
            {
                table.PrimaryKey("PK_Memberships", x => x.Id);
            });

        migrationBuilder.CreateTable(
            name: "Users",
            columns: table => new
            {
                Id = table.Column<Guid>(type: "uniqueidentifier", nullable: false),
                EntraTenantId = table.Column<Guid>(type: "uniqueidentifier", nullable: false),
                EntraObjectId = table.Column<Guid>(type: "uniqueidentifier", nullable: false),
                Email = table.Column<string>(type: "nvarchar(320)", maxLength: 320, nullable: false),
                RowVersion = table.Column<byte[]>(type: "rowversion", rowVersion: true, nullable: false)
            },
            constraints: table =>
            {
                table.PrimaryKey("PK_Users", x => x.Id);
            });

        migrationBuilder.CreateIndex(
            name: "IX_Invitations_Email_Pending",
            table: "Invitations",
            column: "Email",
            unique: true,
            filter: "[Status] = 'Pending'");

        migrationBuilder.CreateIndex(
            name: "IX_Memberships_UserId_Active",
            table: "Memberships",
            column: "UserId",
            unique: true,
            filter: "[Status] = 'Active'");

        migrationBuilder.CreateIndex(
            name: "IX_Memberships_UserId_Status_Covering",
            table: "Memberships",
            columns: new[] { "UserId", "Status" })
            .Annotation("SqlServer:Include", new[] { "Role" });

        migrationBuilder.CreateIndex(
            name: "IX_Users_EntraTenantId_EntraObjectId",
            table: "Users",
            columns: new[] { "EntraTenantId", "EntraObjectId" },
            unique: true);
    }

    /// <inheritdoc />
    protected override void Down(MigrationBuilder migrationBuilder)
    {
        migrationBuilder.Sql("DROP TRIGGER TR_AuditEntries_PreventModification;");

        migrationBuilder.DropTable(
            name: "AuditEntries");

        migrationBuilder.DropTable(
            name: "IdempotencyRecords");

        migrationBuilder.DropTable(
            name: "Invitations");

        migrationBuilder.DropTable(
            name: "Memberships");

        migrationBuilder.DropTable(
            name: "Users");
    }
}
