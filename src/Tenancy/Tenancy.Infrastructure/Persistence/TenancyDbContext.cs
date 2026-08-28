using System.Linq.Expressions;
using Microsoft.EntityFrameworkCore;
using Tenancy.Domain.Abstractions;
using Tenancy.Domain.Auditing;
using Tenancy.Domain.Invitations;
using Tenancy.Domain.Memberships;
using Tenancy.Domain.Tenants;
using Tenancy.Domain.Users;

namespace Tenancy.Infrastructure.Persistence;

/// <summary>
/// The EF Core <see cref="DbContext"/> for the Tenancy service. Applies a single, named
/// global query filter — <c>"TenantFilter"</c> — to every entity implementing
/// <see cref="ITenantOwned"/>, so every LINQ query issued through this context is silently
/// scoped to <see cref="CurrentTenantId"/> unless the filter is explicitly disabled by name
/// (only <c>MembershipDirectory</c> may do so, and only with an audit trail).
/// </summary>
/// <remarks>
/// The filter predicate reads <see cref="CurrentTenantId"/> via a member access on the
/// context instance (<c>this.CurrentTenantId</c>) rather than a captured local variable, so
/// EF Core lifts it into a SQL query parameter that is re-evaluated on every query execution.
/// A captured local would instead be baked into the compiled query cache at model-build time
/// and never change again for the lifetime of the context — silently breaking isolation for a
/// reused context. This is also why this project does not use <c>AddDbContextPool</c>: a pooled
/// context's <see cref="CurrentTenantId"/> must be reset per logical request/scope, which
/// pooling does not guarantee without extra care.
/// </remarks>
public class TenancyDbContext : DbContext
{
    /// <summary>
    /// The tenant that every query issued through this context instance is scoped to. Must be
    /// set by request-scoped DI wiring before any query runs; read by the
    /// <c>"TenantFilter"</c> global query filter applied in <see cref="OnModelCreating"/>.
    /// </summary>
    public TenantId CurrentTenantId { get; set; }

    public TenancyDbContext(DbContextOptions<TenancyDbContext> options)
        : base(options)
    {
    }

    public DbSet<Tenant> Tenants => Set<Tenant>();

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
        configurationBuilder.Properties<TenantId>().HaveConversion<TenantIdConverter>();
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
        modelBuilder.ApplyConfigurationsFromAssembly(typeof(TenancyDbContext).Assembly);

        foreach (var entityType in modelBuilder.Model.GetEntityTypes())
        {
            if (typeof(ITenantOwned).IsAssignableFrom(entityType.ClrType))
            {
                var filter = BuildTenantFilter(entityType.ClrType);
                modelBuilder.Entity(entityType.ClrType).HasQueryFilter("TenantFilter", filter);
            }
        }
    }

    /// <summary>
    /// Builds, via reflection over an expression tree, the lambda
    /// <c>e =&gt; ((ITenantOwned)e).TenantId == this.CurrentTenantId</c> for the given entity CLR
    /// type. Reflection is required because the filter's parameter type varies per entity, so a
    /// generic <c>Expression&lt;Func&lt;T, bool&gt;&gt;</c> cannot be constructed directly in a
    /// non-generic loop over <see cref="Microsoft.EntityFrameworkCore.Metadata.IMutableEntityType"/>
    /// instances. <c>this.CurrentTenantId</c> is a member access on a constant reference to
    /// <c>this</c> (the context instance), which EF Core lifts into a re-evaluated SQL
    /// parameter — not a captured local snapshotted once at model-build time.
    /// </summary>
    private LambdaExpression BuildTenantFilter(Type entityClrType)
    {
        var parameter = Expression.Parameter(entityClrType, "e");

        var tenantOwnedCast = Expression.Convert(parameter, typeof(ITenantOwned));
        var tenantIdAccess = Expression.Property(tenantOwnedCast, nameof(ITenantOwned.TenantId));

        var contextInstance = Expression.Constant(this);
        var currentTenantIdAccess = Expression.Property(contextInstance, nameof(CurrentTenantId));

        var equality = Expression.Equal(tenantIdAccess, currentTenantIdAccess);

        var delegateType = typeof(Func<,>).MakeGenericType(entityClrType, typeof(bool));
        return Expression.Lambda(delegateType, equality, parameter);
    }
}
