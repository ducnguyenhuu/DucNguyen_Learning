using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;
using Identity.Domain.Memberships;

namespace Identity.Infrastructure.Persistence.Configurations;

/// <summary>
/// EF Core configuration for the <see cref="Membership"/> entity.
/// </summary>
/// <remarks>
/// T026 adds one more index to this same file — keep the class open for a second
/// <c>HasIndex(...)</c> call rather than sealing it or doing anything unusual in
/// <see cref="Configure"/>.
/// </remarks>
public class MembershipConfiguration : IEntityTypeConfiguration<Membership>
{
    public void Configure(EntityTypeBuilder<Membership> builder)
    {
        builder.HasKey(m => m.Id);

        // Persisted as strings, not ordinals, so the columns stay human-readable and stable
        // across future enum reordering.
        builder.Property(m => m.Role)
            .HasConversion<string>()
            .IsRequired();

        builder.Property(m => m.Status)
            .HasConversion<string>()
            .IsRequired();

        // Enforces "one active membership per user per tenant" at the database level. A user
        // re-invited after removal gets a new membership row, not a reactivated old one, since
        // Membership.Remove never transitions back to Active.
        builder.HasIndex(m => new { m.TenantId, m.UserId })
            .IsUnique()
            .HasFilter("[Status] = 'Active'")
            .HasDatabaseName("IX_Memberships_TenantId_UserId_Active");

        // Covering index for membership lookup on the hot path (ADR-017: tenant context resolution).
        // Key columns (TenantId, UserId, Status) satisfy the most common query filter, and including
        // Role lets the lookup complete without touching the base table. Not filtered (applies to all
        // statuses) and not unique (distinct purpose from the filtered unique constraint above).
        builder.HasIndex(m => new { m.TenantId, m.UserId, m.Status })
            .IncludeProperties(m => m.Role)
            .HasDatabaseName("IX_Memberships_TenantId_UserId_Status_Covering");

        builder.Property(m => m.RowVersion)
            .IsRowVersion();
    }
}
