using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;
using Tenancy.Domain.Abstractions;
using Tenancy.Domain.Users;

namespace Tenancy.Infrastructure.Persistence.Configurations;

/// <summary>
/// EF Core configuration for the <see cref="User"/> entity.
/// </summary>
public class UserConfiguration : IEntityTypeConfiguration<User>
{
    /// <summary>
    /// Reasonable upper bound for a normalised email address column.
    /// </summary>
    private const int EmailMaxLength = 320;

    public void Configure(EntityTypeBuilder<User> builder)
    {
        builder.HasKey(u => u.Id);

        // The composite (EntraTenantId, EntraObjectId) is the user's real identity for
        // authorization purposes (research.md R2) — must be unique at the database level too.
        builder.HasIndex(u => new { u.EntraTenantId, u.EntraObjectId })
            .IsUnique();

        // EmailAddress is a single-string-wrapping value object; a value converter is simpler
        // here than an owned type since there is only one underlying column.
        builder.Property(u => u.Email)
            .HasConversion(
                email => email.Value,
                value => new EmailAddress(value))
            .HasMaxLength(EmailMaxLength)
            .IsRequired();

        builder.Property(u => u.RowVersion)
            .IsRowVersion();
    }
}
