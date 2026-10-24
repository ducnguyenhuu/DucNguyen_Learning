using Microsoft.EntityFrameworkCore;
using Identity.Application.Abstractions;
using Identity.Domain.Abstractions;
using Identity.Domain.Invitations;
using Identity.Domain.Memberships;

namespace Identity.Infrastructure.Persistence;

/// <summary>
/// <see cref="IdentityDbContext"/>-backed implementation of <see cref="IInvitationRepository"/>
/// (T078), following <see cref="MembershipRepository"/>'s established style.
/// </summary>
public class InvitationRepository : IInvitationRepository
{
    private readonly IdentityDbContext _dbContext;

    public InvitationRepository(IdentityDbContext dbContext)
    {
        _dbContext = dbContext;
    }

    public Task<bool> IsActiveMemberAsync(EmailAddress email, CancellationToken ct)
    {
        return _dbContext.Memberships
            .Where(m => m.Status == MembershipStatus.Active)
            .Join(_dbContext.Users, m => m.UserId, u => u.Id, (m, u) => u.Email)
            .AnyAsync(e => e == email, ct);
    }

    public Task<bool> HasPendingInvitationAsync(EmailAddress email, CancellationToken ct)
    {
        return _dbContext.Invitations
            .AnyAsync(i => i.Email == email && i.Status == InvitationStatus.Pending, ct);
    }

    public async Task AddAsync(Invitation invitation, CancellationToken ct)
    {
        _dbContext.Invitations.Add(invitation);

        try
        {
            await _dbContext.SaveChangesAsync(ct);
        }
        catch (DbUpdateException ex)
        {
            throw new ConcurrencyConflictException(
                "Failed to add invitation: a concurrent insert with the same unique key won the race.",
                ex);
        }
    }

    public Task<Invitation?> FindByTokenHashAsync(string tokenHashBase64, CancellationToken ct)
    {
        return _dbContext.Invitations
            .SingleOrDefaultAsync(i => i.TokenHash == tokenHashBase64, ct);
    }

    public async Task SaveAcceptedAsync(Invitation invitation, Membership membership, CancellationToken ct)
    {
        // The invitation is already tracked (loaded by FindByTokenHashAsync and mutated by
        // Accept), so one SaveChangesAsync writes its status change and the new membership in
        // the same implicit transaction.
        _dbContext.Memberships.Add(membership);
        await _dbContext.SaveChangesAsync(ct);
    }

    public async Task<IReadOnlyList<Invitation>> GetAllPendingAsync(CancellationToken ct)
    {
        return await _dbContext.Invitations
            .Where(i => i.Status == InvitationStatus.Pending)
            .ToListAsync(ct);
    }

    public Task<Invitation?> GetByIdAsync(InvitationId id, CancellationToken ct)
    {
        return _dbContext.Invitations.SingleOrDefaultAsync(i => i.Id == id, ct);
    }

    public Task SaveAsync(Invitation invitation, CancellationToken ct)
    {
        return _dbContext.SaveChangesAsync(ct);
    }
}
