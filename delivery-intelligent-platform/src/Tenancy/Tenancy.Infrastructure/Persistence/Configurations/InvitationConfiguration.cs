using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;
using Tenancy.Domain.Abstractions;
using Tenancy.Domain.Invitations;

namespace Tenancy.Infrastructure.Persistence.Configurations;

/// <summary>
/// EF Core configuration for the <see cref="Invitation"/> entity.
/// </summary>
public class InvitationConfiguration : IEntityTypeConfiguration<Invitation>
{
    /// <summary>
    /// Reasonable upper bound for a normalised email address column.
    /// </summary>
    private const int EmailMaxLength = 320;

    /// <summary>
    /// <see cref="Invitation.TokenHash"/> stores the hex-encoded SHA-256 digest of the
    /// invitation token — always exactly 64 hex characters.
    /// </summary>
    private const int TokenHashLength = 64;

    public void Configure(EntityTypeBuilder<Invitation> builder)
    {
        builder.HasKey(i => i.Id);

        // Persisted as strings, not ordinals, so the columns stay human-readable and stable
        // across future enum reordering.
        builder.Property(i => i.Role)
            .HasConversion<string>()
            .IsRequired();

        builder.Property(i => i.Status)
            .HasConversion<string>()
            .IsRequired();

        // Same EmailAddress mapping approach as UserConfiguration, for consistency.
        builder.Property(i => i.Email)
            .HasConversion(
                email => email.Value,
                value => new EmailAddress(value))
            .HasMaxLength(EmailMaxLength)
            .IsRequired();

        builder.Property(i => i.TokenHash)
            .HasMaxLength(TokenHashLength)
            .IsRequired();

        // Enforces "one pending invitation per email per tenant" — makes FR-020's idempotency
        // correct even if the idempotency layer is bypassed (data-model.md).
        builder.HasIndex(i => new { i.TenantId, i.Email })
            .IsUnique()
            .HasFilter("[Status] = 'Pending'")
            .HasDatabaseName("IX_Invitations_TenantId_Email_Pending");

        builder.Property(i => i.ExpiresAtUtc)
            .IsRequired();

        builder.Property(i => i.RowVersion)
            .IsRowVersion();
    }
}
