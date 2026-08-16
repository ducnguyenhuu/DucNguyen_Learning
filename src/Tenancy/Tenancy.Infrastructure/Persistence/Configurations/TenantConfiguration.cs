using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;
using Tenancy.Domain.Tenants;

namespace Tenancy.Infrastructure.Persistence.Configurations;

/// <summary>
/// EF Core configuration for the <see cref="Tenant"/> aggregate root.
/// </summary>
public class TenantConfiguration : IEntityTypeConfiguration<Tenant>
{
    public void Configure(EntityTypeBuilder<Tenant> builder)
    {
        builder.HasKey(t => t.Id);

        builder.Property(t => t.DisplayName)
            .IsRequired()
            .HasMaxLength(Tenant.DisplayNameMaxLength);

        // Persisted as a string, not an ordinal, so the column stays human-readable and stable
        // across future enum reordering.
        builder.Property(t => t.Status)
            .HasConversion<string>()
            .IsRequired();

        // TenantSettings currently has no properties of its own (intentionally minimal, per its
        // doc comment — grows as tenant-level configuration needs emerge). EF Core's complex-type
        // mapping (and owned-entity mapping) both require at least one persisted property, so
        // there is nothing to configure yet; explicitly ignore it so EF doesn't try to map an
        // empty type, and map it (as ComplexProperty or OwnsOne) once it gains its first property.
        builder.Ignore(t => t.Settings);

        // Explicitly NOT unique — DisplayName is not globally unique, per T017's design.

        builder.Property(t => t.RowVersion)
            .IsRowVersion();

        builder.Property(t => t.CreatedAtUtc)
            .IsRequired();
    }
}
