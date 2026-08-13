using System.Data;
using Microsoft.EntityFrameworkCore;
using Tenancy.Application.Abstractions;
using Tenancy.Domain.Abstractions;
using Tenancy.Domain.Memberships;
using Tenancy.Domain.Tenants;

namespace Tenancy.Infrastructure.Persistence;

/// <summary>
/// <see cref="TenancyDbContext"/>-backed implementation of <see cref="IMembershipRepository"/>.
/// </summary>
/// <remarks>
/// <b>Transactional-protection choice: Option B — an explicit exclusive row lock on the tenant's
/// row (<c>SELECT 1 FROM Tenants WHERE Id = @tenantId WITH (UPDLOCK, HOLDLOCK)</c>), taken
/// <em>before</em> counting active administrators, rather than Option A
/// (a <see cref="IsolationLevel.Serializable"/> transaction for the whole operation).</b>
/// </remarks>
/// <remarks>
/// <para>
/// <b>Why row lock over SERIALIZABLE.</b> Both options close the same race (T068's two
/// concurrent removals each observing a stale administrator count of 2). SERIALIZABLE would
/// correctly serialize the two transactions too, but it does so by taking range locks over
/// <em>every</em> row this transaction's queries touch (the whole administrator-count read),
/// escalating the blast radius and the chance of lock-timeout/deadlock victim selection under
/// load — for a data model that at this stage may run every write at the default isolation level
/// elsewhere. The row lock is the narrower tool: only the single <see cref="Tenant"/> row this
/// operation cares about is locked, and only for the duration of this one transaction, so it
/// serializes concurrent removals for <em>that tenant</em> without affecting throughput for any
/// other tenant's concurrent writes. This also matches data-model.md's own second-listed option
/// ("take an application lock on the tenant row... before counting") and is the same
/// UPDLOCK/HOLDLOCK-before-counting shape the task brief's Option B spells out verbatim.
/// </para>
/// <para>
/// <b>Mechanics.</b> <c>UPDLOCK</c> takes an update lock immediately (rather than a shared lock
/// that could itself deadlock against another reader upgrading to a write lock) and <c>HOLDLOCK</c>
/// is the T-SQL equivalent of <c>SERIALIZABLE</c> scoped to just this one hint, holding the lock
/// until the enclosing transaction commits or rolls back. Two concurrent
/// <see cref="RemoveMembershipAsync"/> calls targeting the same tenant therefore cannot both pass
/// this line: the second caller blocks on the lock until the first's transaction resolves, and by
/// the time it acquires the lock it re-counts administrators against the *post-first-commit*
/// state — so if the first removal already reduced the count to one, the second correctly fails
/// <see cref="TenantAdministration.EnsureRemovalAllowed"/> instead of racing past it.
/// </para>
/// </remarks>
public class MembershipRepository : IMembershipRepository
{
    private readonly TenancyDbContext _dbContext;
    private readonly IClock _clock;

    public MembershipRepository(TenancyDbContext dbContext, IClock clock)
    {
        _dbContext = dbContext;
        _clock = clock;
    }

    public async Task<IReadOnlyList<Membership>> GetActiveMembersAsync(CancellationToken ct)
    {
        // No IgnoreQueryFilters here (unlike RemoveMembershipAsync below): the tenant-scoping
        // global query filter is exactly what's wanted for this read — TenancyDbContext.CurrentTenantId
        // has already been resolved to the caller's tenant by upstream middleware (ADR-017), the
        // same ambient-scoping reliance GetTenant (T055) documents.
        return await _dbContext.Memberships
            .Where(m => m.Status == MembershipStatus.Active)
            .ToListAsync(ct);
    }

    public Task<Membership?> GetActiveMembershipForUserAsync(UserId userId, CancellationToken ct)
    {
        return _dbContext.Memberships
            .SingleOrDefaultAsync(m => m.UserId == userId && m.Status == MembershipStatus.Active, ct);
    }

    public async Task RemoveMembershipAsync(MembershipId membershipId, CancellationToken ct)
    {
        // IgnoreQueryFilters: the tenant-scoping filter on Memberships requires
        // TenancyDbContext.CurrentTenantId to already be set to the right tenant, which the
        // caller has no reason to know ahead of a lookup by membership id alone. This method is
        // the one place responsible for discovering the owning tenant and then scoping itself to
        // it explicitly.
        var membership = await _dbContext.Memberships
            .IgnoreQueryFilters()
            .SingleOrDefaultAsync(m => m.Id == membershipId, ct);

        if (membership is null)
        {
            throw new DomainException($"Membership '{membershipId.Value}' was not found.");
        }

        _dbContext.CurrentTenantId = membership.TenantId;

        await using var transaction = await _dbContext.Database.BeginTransactionAsync(
            IsolationLevel.ReadCommitted,
            ct);

        // Exclusive row lock on the tenant, taken before counting administrators, so a second
        // concurrent removal targeting the same tenant blocks here until this transaction commits
        // or rolls back — see the type-level remarks for why this (Option B) was chosen over a
        // SERIALIZABLE transaction (Option A).
        await _dbContext.Database.ExecuteSqlInterpolatedAsync(
            $"SELECT 1 FROM Tenants WITH (UPDLOCK, HOLDLOCK) WHERE Id = {membership.TenantId.Value}",
            ct);

        var activeMemberships = await _dbContext.Memberships
            .IgnoreQueryFilters()
            .Where(m => m.TenantId == membership.TenantId && m.Status == MembershipStatus.Active)
            .ToListAsync(ct);

        var membershipToRemove = activeMemberships.SingleOrDefault(m => m.Id == membershipId);

        if (membershipToRemove is null)
        {
            // Already removed (e.g. by a caller that raced us and lost this method's own lock
            // wait, or a prior call) — nothing left to do.
            await transaction.CommitAsync(ct);
            return;
        }

        TenantAdministration.EnsureRemovalAllowed(activeMemberships, membershipToRemove);

        membershipToRemove.Remove(_clock);

        await _dbContext.SaveChangesAsync(ct);
        await transaction.CommitAsync(ct);
    }

    public Task SaveAsync(Membership membership, CancellationToken ct)
    {
        return _dbContext.SaveChangesAsync(ct);
    }
}
