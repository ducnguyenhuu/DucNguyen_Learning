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

    public void Configure(EntityTypeBuilder<IdempotencyRecord> builder)
    {
        // The composite (TenantId, Endpoint, Key) is the primary key — the uniqueness of this
        // key IS the concurrency control, and scoping by tenant prevents cross-tenant key
        // probing. There is deliberately no surrogate Id.
        builder.HasKey(r => new { r.TenantId, r.Endpoint, r.Key });

        builder.Property(r => r.Endpoint)
            .IsRequired()
            .HasMaxLength(EndpointMaxLength);

        builder.Property(r => r.Key)
            .IsRequired()
            .HasMaxLength(KeyMaxLength);

        // No HasMaxLength for ResponseBody — EF Core maps a plain string to nvarchar(max) on
        // SQL Server by default when no max length is specified, which is fine for a cached
        // response payload of arbitrary size.
        builder.Property(r => r.ResponseBody);

        builder.Property(r => r.ResponseStatusCode)
            .IsRequired();

        builder.Property(r => r.CreatedAtUtc)
            .IsRequired();
    }
}
