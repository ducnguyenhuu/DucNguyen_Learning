using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;

namespace Tenancy.Infrastructure.Persistence.Configurations;

/// <summary>
/// EF Core configuration for the <see cref="IdempotencyRecord"/> infrastructure entity.
/// </summary>
public class IdempotencyRecordConfiguration : IEntityTypeConfiguration<IdempotencyRecord>
{
    /// <summary>
    /// Sane upper bound for <see cref="IdempotencyRecord.Endpoint"/> — comfortably covers any
    /// realistic route template (method + path + placeholders) without being unbounded.
    /// </summary>
    private const int EndpointMaxLength = 256;

    /// <summary>
    /// Sane upper bound for <see cref="IdempotencyRecord.Key"/> — comfortably covers client
    /// idempotency keys (typically GUIDs or short opaque tokens) without being unbounded.
    /// </summary>
    private const int KeyMaxLength = 256;

    /// <summary>
    /// Fixed length of a SHA-256 digest in bytes.
    /// </summary>
    private const int RequestHashLength = 32;

    public void Configure(EntityTypeBuilder<IdempotencyRecord> builder)
    {
        // The composite (TenantId, Endpoint, Key) is the primary key — the uniqueness of this
        // key IS the concurrency control, and scoping by tenant prevents cross-tenant key
        // probing. There is deliberately no surrogate Id.
        //
        // NOTE: TenantId is nullable (see IdempotencyRecord's class remarks — POST /tenants has
        // no tenant context yet). EF Core / SQL Server allow a nullable column to participate in
        // a composite primary key, but the column is still implicitly marked NOT NULL by the PK
        // constraint itself — SQL Server does not support NULL in ANY column that is part of a
        // PRIMARY KEY, composite or not. That means TenantId is only truly "nullable" at the CLR
        // level for the ITenantOwned-removal reasoning above; at the storage level the PK
        // constraint forces it to NOT NULL. This is a known SQL Server limitation worth flagging:
        // if the pre-tenant (POST /tenants) case is ever hit for real, this composite PK as
        // written will reject a NULL TenantId at the database level. Revisit if/when T056 wires
        // up the no-tenant-context path against a real database — a filtered unique index or a
        // sentinel TenantId may be needed instead of relying on NULL here.
        builder.HasKey(r => new { r.TenantId, r.Endpoint, r.Key });

        builder.Property(r => r.Endpoint)
            .IsRequired()
            .HasMaxLength(EndpointMaxLength);

        builder.Property(r => r.Key)
            .IsRequired()
            .HasMaxLength(KeyMaxLength);

        builder.Property(r => r.RequestHash)
            .IsRequired()
            .HasMaxLength(RequestHashLength);

        // tinyint per data-model.md — a compact numeric mapping, not the string mapping used for
        // the domain enums (Role/TenantStatus/etc.) elsewhere in this project.
        builder.Property(r => r.Status)
            .HasConversion<byte>()
            .IsRequired();

        builder.Property(r => r.CreatedByUserId)
            .IsRequired();

        // No HasMaxLength for ResponseBody — EF Core maps a plain string to nvarchar(max) on
        // SQL Server by default when no max length is specified, which is fine for a cached
        // response payload of arbitrary size.
        builder.Property(r => r.ResponseBody);

        builder.Property(r => r.ResourceLocation);

        builder.Property(r => r.StatusCode);

        builder.Property(r => r.CreatedAtUtc)
            .IsRequired();

        builder.Property(r => r.ExpiresAtUtc)
            .IsRequired();
    }
}
