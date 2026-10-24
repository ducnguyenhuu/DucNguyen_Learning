using Microsoft.EntityFrameworkCore;
using Identity.Domain.Abstractions;
using Identity.Domain.Auditing;
using Identity.Domain.Invitations;
using Identity.Domain.Memberships;
using Identity.Domain.Users;

namespace Identity.Infrastructure.Persistence;

/// <summary>
/// The EF Core <see cref="DbContext"/> for the Identity service: users, memberships, invitations,
/// the audit log, and idempotency records. One deployment serves one organization (ADR-025), so
/// no query filter scopes these tables.
/// </summary>
/// <remarks>
/// Registered with <c>AddDbContext</c> (scoped), not <c>AddDbContextPool</c>: the audit writer and
/// the repositories rely on sharing one request-scoped instance so a single
/// <c>SaveChangesAsync</c> flushes a use case's entity changes and its staged audit entry together.
/// </remarks>
public class IdentityDbContext : DbContext
{
    public IdentityDbContext(DbContextOptions<IdentityDbContext> options)
        : base(options)
    {
    }

    public DbSet<User> Users => Set<User>();

    public DbSet<Membership> Memberships => Set<Membership>();

    public DbSet<Invitation> Invitations => Set<Invitation>();

    public DbSet<IdempotencyRecord> IdempotencyRecords => Set<IdempotencyRecord>();

    public DbSet<AuditEntry> AuditEntries => Set<AuditEntry>();

    /// <summary>
    /// Registers the value converters for the project's strongly-typed ID structs once, globally,
    /// rather than repeating <c>HasConversion</c> in every entity configuration — see
    /// <see cref="StronglyTypedIdConverters"/>.
    /// </summary>
    protected override void ConfigureConventions(ModelConfigurationBuilder configurationBuilder)
    {
        configurationBuilder.Properties<UserId>().HaveConversion<UserIdConverter>();
        configurationBuilder.Properties<MembershipId>().HaveConversion<MembershipIdConverter>();
        configurationBuilder.Properties<InvitationId>().HaveConversion<InvitationIdConverter>();
        configurationBuilder.Properties<AuditEntryId>().HaveConversion<AuditEntryIdConverter>();
    }

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        base.OnModelCreating(modelBuilder);

        // Applies every IEntityTypeConfiguration<T> in this assembly (Configurations/), rather
        // than listing each one by hand — new entities pick up their configuration automatically
        // as long as they follow the one-configuration-class-per-entity convention.
        modelBuilder.ApplyConfigurationsFromAssembly(typeof(IdentityDbContext).Assembly);
    }
}
