using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Diagnostics;
using Tenancy.Domain.Abstractions;

namespace Tenancy.Infrastructure.Persistence.Interceptors;

/// <summary>
/// Write-side half of tenant isolation. <see cref="TenancyDbContext"/>'s <c>"TenantFilter"</c>
/// global query filter only scopes reads (<c>SELECT</c>) — EF Core does not apply query filters
/// to <c>INSERT</c>/<c>UPDATE</c>/<c>DELETE</c> (tracked upstream as efcore#24122). This
/// interceptor closes that gap by inspecting every tracked <see cref="ITenantOwned"/> entry
/// immediately before <c>SaveChanges</c>/<c>SaveChangesAsync</c> reaches the database:
/// <list type="bullet">
/// <item>
/// <description><see cref="EntityState.Added"/>: stamps the entry's <c>TenantId</c> with the
/// ambient <see cref="TenancyDbContext.CurrentTenantId"/>, so a caller cannot insert a row under
/// a tenant other than the one the current context is scoped to.</description>
/// </item>
/// <item>
/// <description><see cref="EntityState.Modified"/> or <see cref="EntityState.Deleted"/>: rejects
/// the operation with a <see cref="DomainException"/> if the entry's <b>original</b>
/// <c>TenantId</c> (the value read from the database) does not match the ambient
/// <see cref="TenancyDbContext.CurrentTenantId"/> — this is the "ambient mismatch" check.</description>
/// </item>
/// <item>
/// <description><see cref="EntityState.Modified"/> additionally: rejects the operation with a
/// <see cref="DomainException"/> if the entry's <b>current</b> <c>TenantId</c> differs from its
/// <b>original</b> <c>TenantId</c> — i.e. someone tried to reassign the row to a different
/// tenant. This is a distinct check from the ambient-mismatch one above: an entry could have
/// <c>original == ambient</c> (so the ambient check passes) yet <c>current != original</c> (a
/// reassignment attempt).</description>
/// </item>
/// </list>
/// </summary>
/// <remarks>
/// <para>
/// This is written against <see cref="TenancyDbContext"/> directly rather than an abstraction
/// over "any <see cref="DbContext"/> with a tenant property" — this project has exactly one
/// <see cref="DbContext"/>, so a generic mechanism would be speculative (YAGNI).
/// </para>
/// <para>
/// On the reassignment check: <see cref="Tenancy.Domain.Memberships.Membership"/> and
/// <see cref="Tenancy.Domain.Invitations.Invitation"/> both declare <c>TenantId</c> as
/// <c>{ get; }</c> with no public setter anywhere in the domain assembly, so ordinary C# code
/// cannot reassign <c>TenantId</c> on an existing instance — the domain model itself already
/// makes this immutable, and the check below is unreachable through the public domain API.
/// It is kept (rather than omitted as dead code) because EF Core's change tracker exposes a
/// second, lower-level mutation path that bypasses the CLR property entirely:
/// <c>entry.CurrentValues[nameof(ITenantOwned.TenantId)] = ...</c> (or the strongly-typed
/// <c>entry.Property(...).CurrentValue</c> equivalent) writes directly to the tracked snapshot
/// via reflection/backing-field access, independent of whether a public setter exists. Any code
/// with a reference to the <see cref="DbContext"/> — a future refactor, a test helper, a
/// misguided "quick fix" — could reach that path, so this check is defense-in-depth against a
/// real, if currently unused, attack surface rather than genuinely dead code.
/// </para>
/// </remarks>
public sealed class TenantSaveChangesInterceptor : SaveChangesInterceptor
{
    public override async ValueTask<InterceptionResult<int>> SavingChangesAsync(
        DbContextEventData eventData,
        InterceptionResult<int> result,
        CancellationToken cancellationToken = default)
    {
        EnforceTenantIsolation(eventData.Context);

        return await base.SavingChangesAsync(eventData, result, cancellationToken);
    }

    public override InterceptionResult<int> SavingChanges(
        DbContextEventData eventData,
        InterceptionResult<int> result)
    {
        EnforceTenantIsolation(eventData.Context);

        return base.SavingChanges(eventData, result);
    }

    private static void EnforceTenantIsolation(DbContext? context)
    {
        if (context is not TenancyDbContext tenancyDbContext)
        {
            return;
        }

        var ambientTenantId = tenancyDbContext.CurrentTenantId;

        foreach (var entry in tenancyDbContext.ChangeTracker.Entries())
        {
            if (entry.Entity is not ITenantOwned)
            {
                continue;
            }

            switch (entry.State)
            {
                case EntityState.Added:
                    entry.CurrentValues[nameof(ITenantOwned.TenantId)] = ambientTenantId;
                    break;

                case EntityState.Modified:
                case EntityState.Deleted:
                    var originalTenantId = (TenantId)entry.OriginalValues[nameof(ITenantOwned.TenantId)]!;

                    if (originalTenantId != ambientTenantId)
                    {
                        throw new DomainException(
                            $"Cannot {entry.State.ToString().ToLowerInvariant()} entity of type " +
                            $"'{entry.Entity.GetType().Name}' owned by tenant '{originalTenantId.Value}' " +
                            $"while the current context is scoped to tenant '{ambientTenantId.Value}'.");
                    }

                    if (entry.State == EntityState.Modified)
                    {
                        var currentTenantId = (TenantId)entry.CurrentValues[nameof(ITenantOwned.TenantId)]!;

                        if (currentTenantId != originalTenantId)
                        {
                            throw new DomainException(
                                $"Cannot reassign entity of type '{entry.Entity.GetType().Name}' " +
                                $"from tenant '{originalTenantId.Value}' to tenant " +
                                $"'{currentTenantId.Value}'. TenantId is immutable.");
                        }
                    }

                    break;
            }
        }
    }
}
