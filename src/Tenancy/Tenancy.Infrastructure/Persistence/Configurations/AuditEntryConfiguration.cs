using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;
using Tenancy.Domain.Auditing;

namespace Tenancy.Infrastructure.Persistence.Configurations;

/// <summary>
/// EF Core configuration for the <see cref="AuditEntry"/> entity.
/// </summary>
/// <remarks>
/// <see cref="AuditEntry"/> deliberately does not implement <c>ITenantOwned</c> — its
/// <see cref="AuditEntry.TenantId"/> is nullable (the unauthenticated-refusal case has no
/// tenant), which does not fit the shape assumed by
/// <see cref="TenancyDbContext.BuildTenantFilter"/>. No global query filter is applied here.
/// </remarks>
public class AuditEntryConfiguration : IEntityTypeConfiguration<AuditEntry>
{
    public void Configure(EntityTypeBuilder<AuditEntry> builder)
    {
        builder.HasKey(a => a.Id);

        // TenantId and ActorUserId map through the global TenantId/UserId converters
        // registered in TenancyDbContext.ConfigureConventions; being nullable value types
        // (TenantId?/UserId?), EF Core maps them to nullable columns automatically without a
        // redundant per-property HasConversion call here.

        builder.Property(a => a.Action)
            .IsRequired();

        builder.Property(a => a.ResourceType)
            .IsRequired();

        builder.Property(a => a.ResourceId)
            .IsRequired();
    }
}
