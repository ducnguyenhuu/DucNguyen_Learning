using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Identity.Infrastructure.Migrations;

/// <inheritdoc />
public partial class IdempotencyRecordCorrection : Migration
{
    /// <inheritdoc />
    protected override void Up(MigrationBuilder migrationBuilder)
    {
        migrationBuilder.DropColumn(
            name: "ResponseStatusCode",
            table: "IdempotencyRecords");

        migrationBuilder.AddColumn<Guid>(
            name: "CreatedByUserId",
            table: "IdempotencyRecords",
            type: "uniqueidentifier",
            nullable: false,
            defaultValue: new Guid("00000000-0000-0000-0000-000000000000"));

        migrationBuilder.AddColumn<DateTimeOffset>(
            name: "ExpiresAtUtc",
            table: "IdempotencyRecords",
            type: "datetimeoffset",
            nullable: false,
            defaultValue: new DateTimeOffset(new DateTime(1, 1, 1, 0, 0, 0, 0, DateTimeKind.Unspecified), new TimeSpan(0, 0, 0, 0, 0)));

        migrationBuilder.AddColumn<byte[]>(
            name: "RequestHash",
            table: "IdempotencyRecords",
            type: "varbinary(32)",
            maxLength: 32,
            nullable: false,
            defaultValue: new byte[0]);

        migrationBuilder.AddColumn<string>(
            name: "ResourceLocation",
            table: "IdempotencyRecords",
            type: "nvarchar(max)",
            nullable: true);

        migrationBuilder.AddColumn<byte>(
            name: "Status",
            table: "IdempotencyRecords",
            type: "tinyint",
            nullable: false,
            defaultValue: (byte)0);

        migrationBuilder.AddColumn<int>(
            name: "StatusCode",
            table: "IdempotencyRecords",
            type: "int",
            nullable: true);
    }

    /// <inheritdoc />
    protected override void Down(MigrationBuilder migrationBuilder)
    {
        migrationBuilder.DropColumn(
            name: "CreatedByUserId",
            table: "IdempotencyRecords");

        migrationBuilder.DropColumn(
            name: "ExpiresAtUtc",
            table: "IdempotencyRecords");

        migrationBuilder.DropColumn(
            name: "RequestHash",
            table: "IdempotencyRecords");

        migrationBuilder.DropColumn(
            name: "ResourceLocation",
            table: "IdempotencyRecords");

        migrationBuilder.DropColumn(
            name: "Status",
            table: "IdempotencyRecords");

        migrationBuilder.DropColumn(
            name: "StatusCode",
            table: "IdempotencyRecords");

        migrationBuilder.AddColumn<int>(
            name: "ResponseStatusCode",
            table: "IdempotencyRecords",
            type: "int",
            nullable: false,
            defaultValue: 0);
    }
}
