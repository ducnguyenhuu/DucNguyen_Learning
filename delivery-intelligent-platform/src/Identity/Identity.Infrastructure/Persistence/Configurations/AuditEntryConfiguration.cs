using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;
using Identity.Domain.Auditing;

namespace Identity.Infrastructure.Persistence.Configurations;

/// <summary>
/// EF Core configuration for the <see cref="AuditEntry"/> entity.
/// </summary>
public class AuditEntryConfiguration : IEntityTypeConfiguration<AuditEntry>
{
    public void Configure(EntityTypeBuilder<AuditEntry> builder)
    {
        builder.HasKey(a => a.Id);

        // ActorUserId maps through the global UserId converter registered in
        // IdentityDbContext.ConfigureConventions; being a nullable value type (UserId?), EF Core
        // maps it to a nullable column automatically without a redundant per-property
        // HasConversion call here.
        //
        // The explicit Property() calls below (for ActorUserId and OccurredAtUtc) are
        // required, not redundant: AuditEntry's constructor is private, so EF Core's design-time
        // model building relies on constructor binding to materialize instances, which only
        // considers properties it already knows are mapped. Without at least one explicit
        // reference to each of these two, EF Core's convention-based discovery never picks them
        // up before constructor binding runs, and `dotnet ef migrations add` fails with "No
        // suitable constructor was found for the type 'AuditEntry'". Id/Action/ResourceType/
        // ResourceId don't need this because HasKey (for Id) and IsRequired (for the other three,
        // below) already make an explicit reference.
        builder.Property(a => a.ActorUserId);
        builder.Property(a => a.OccurredAtUtc)
            .IsRequired();

        builder.Property(a => a.Action)
            .IsRequired();

        builder.Property(a => a.ResourceType)
            .IsRequired();

        builder.Property(a => a.ResourceId)
            .IsRequired();
    }
}
