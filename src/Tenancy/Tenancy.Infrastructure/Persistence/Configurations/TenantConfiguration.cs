using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;
using Tenancy.Domain.Tenants;

namespace Tenancy.Infrastructure.Persistence.Configurations;

/// <summary>
/// EF Core configuration for the <see cref="Tenant"/> aggregate root.
/// </summary>
public class TenantConfiguration : IEntityTypeConfiguration<Tenant>
{
    /// <summary>
    /// Reasonable upper bound for a tenant display name. Not enforced anywhere else in the
    /// domain — chosen here purely as a sane database column bound.
    /// </summary>
    private const int DisplayNameMaxLength = 200;

    public void Configure(EntityTypeBuilder<Tenant> builder)
    {
        builder.HasKey(t => t.Id);

        builder.Property(t => t.DisplayName)
            .IsRequired()
            .HasMaxLength(DisplayNameMaxLength);

        // Persisted as a string, not an ordinal, so the column stays human-readable and stable
        // across future enum reordering.
        builder.Property(t => t.Status)
            .HasConversion<string>()
            .IsRequired();

        // TenantSettings has no identity of its own — configure it as an owned type rather than
        // a separate table/aggregate.
        builder.OwnsOne(t => t.Settings);

        // Explicitly NOT unique — DisplayName is not globally unique, per T017's design.

        builder.Property(t => t.RowVersion)
            .IsRowVersion();
    }
}
