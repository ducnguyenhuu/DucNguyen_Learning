using System.Data;
using Microsoft.EntityFrameworkCore;
using Identity.Application.Abstractions;
using Identity.Domain.Abstractions;
using Identity.Domain.Memberships;

namespace Identity.Infrastructure.Persistence;

/// <summary>
/// <see cref="IdentityDbContext"/>-backed implementation of <see cref="IMembershipRepository"/>.
/// </summary>
/// <remarks>
/// <para>
/// <b>Serializing the guarded writes: an exclusive application lock
/// (<c>sp_getapplock</c>, resource <see cref="AdministratorsLockResource"/>, owned by the
/// transaction), taken <em>before</em> counting memberships.</b> Both
/// <see cref="RemoveMembershipAsync"/> (the last-administrator invariant) and
/// <see cref="TryAddFirstAdministratorAsync"/> (bootstrap) read a count and then write based on
/// it, so two concurrent callers could each observe the same stale count. Taking the same lock
/// first makes the second caller wait until the first transaction commits or rolls back, and
/// then re-count against the post-commit state.
/// </para>
/// <para>
/// <b>Why an application lock, not a row lock or SERIALIZABLE.</b> Until ADR-025 this repository
/// locked the owning tenant's row, which every membership had. There is no such row now, and the
/// thing being protected — "the set of active administrators" — is not one row. SERIALIZABLE
/// would also close the race, but it takes range locks over every row the count touches, which
/// widens the blast radius and the chance of deadlock-victim selection. An application lock names
/// exactly the invariant being protected, is released automatically when the transaction ends,
/// and blocks no reader or unrelated writer.
/// </para>
/// </remarks>
public class MembershipRepository : IMembershipRepository
{
    /// <summary>
    /// The <c>sp_getapplock</c> resource name shared by every write that depends on the count of
    /// active memberships or administrators.
    /// </summary>
    public const string AdministratorsLockResource = "Identity.Memberships.Administrators";

    private readonly IdentityDbContext _dbContext;
    private readonly IClock _clock;

    public MembershipRepository(IdentityDbContext dbContext, IClock clock)
    {
        _dbContext = dbContext;
        _clock = clock;
    }

    public async Task<IReadOnlyList<Membership>> GetActiveMembersAsync(CancellationToken ct)
    {
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
        await using var transaction = await _dbContext.Database.BeginTransactionAsync(
            IsolationLevel.ReadCommitted,
            ct);

        // Taken before counting administrators, so a second concurrent removal blocks here until
        // this transaction commits or rolls back — see the type-level remarks.
        await AcquireAdministratorsLockAsync(ct);

        var activeMemberships = await _dbContext.Memberships
            .Where(m => m.Status == MembershipStatus.Active)
            .ToListAsync(ct);

        var membershipToRemove = activeMemberships.SingleOrDefault(m => m.Id == membershipId);

        if (membershipToRemove is null)
        {
            // Already removed (e.g. by a caller that raced us and won this method's own lock
            // wait, or a prior call) — nothing left to do.
            await transaction.CommitAsync(ct);
            return;
        }

        OrganizationAdministration.EnsureRemovalAllowed(activeMemberships, membershipToRemove);

        membershipToRemove.Remove(_clock);

        await _dbContext.SaveChangesAsync(ct);
        await transaction.CommitAsync(ct);
    }

    public async Task<bool> TryAddFirstAdministratorAsync(Membership administratorMembership, CancellationToken ct)
    {
        await using var transaction = await _dbContext.Database.BeginTransactionAsync(
            IsolationLevel.ReadCommitted,
            ct);

        // Same lock as RemoveMembershipAsync: two first sign-ins racing to bootstrap must not both
        // observe "no members yet".
        await AcquireAdministratorsLockAsync(ct);

        var hasMembers = await _dbContext.Memberships
            .AnyAsync(m => m.Status == MembershipStatus.Active, ct);

        if (hasMembers)
        {
            await transaction.RollbackAsync(ct);
            return false;
        }

        _dbContext.Memberships.Add(administratorMembership);

        await _dbContext.SaveChangesAsync(ct);
        await transaction.CommitAsync(ct);
        return true;
    }

    public Task SaveAsync(Membership membership, CancellationToken ct)
    {
        return _dbContext.SaveChangesAsync(ct);
    }

    /// <summary>
    /// Takes the exclusive, transaction-owned application lock described in the type-level
    /// remarks. Must be called inside an open transaction; the lock is released when it ends.
    /// </summary>
    /// <remarks>
    /// <c>sp_getapplock</c> reports failure (deadlock victim, cancellation, error) through a
    /// negative return code, not an exception, so the result is checked and turned into one.
    /// Proceeding without the lock would silently reopen the race this method exists to close.
    /// </remarks>
    private Task AcquireAdministratorsLockAsync(CancellationToken ct)
    {
        return _dbContext.Database.ExecuteSqlInterpolatedAsync(
            $"""
            DECLARE @result int;
            EXEC @result = sp_getapplock @Resource = {AdministratorsLockResource}, @LockMode = 'Exclusive', @LockOwner = 'Transaction';
            IF @result < 0 THROW 50000, 'Could not acquire the memberships application lock.', 1;
            """,
            ct);
    }
}
