using Microsoft.EntityFrameworkCore;
using Identity.Application.Abstractions;
using Identity.Domain.Abstractions;
using Identity.Domain.Users;

namespace Identity.Infrastructure.Persistence;

/// <summary>
/// <see cref="IdentityDbContext"/>-backed implementation of <see cref="IUserRepository"/>.
/// </summary>
public class UserRepository : IUserRepository
{
    private readonly IdentityDbContext _dbContext;

    public UserRepository(IdentityDbContext dbContext)
    {
        _dbContext = dbContext;
    }

    public Task<User?> FindByEntraIdentityAsync(Guid entraTenantId, Guid entraObjectId, CancellationToken ct)
    {
        return _dbContext.Users
            .SingleOrDefaultAsync(
                u => u.EntraTenantId == entraTenantId && u.EntraObjectId == entraObjectId,
                ct);
    }

    public async Task AddAsync(User user, CancellationToken ct)
    {
        _dbContext.Users.Add(user);

        try
        {
            await _dbContext.SaveChangesAsync(ct);
        }
        catch (DbUpdateException ex)
        {
            throw new ConcurrencyConflictException(
                "Failed to add user: a concurrent insert with the same Entra identity won the race.",
                ex);
        }
    }

    public async Task<IReadOnlyList<User>> FindByIdsAsync(IReadOnlyCollection<UserId> userIds, CancellationToken ct)
    {
        return await _dbContext.Users
            .Where(u => userIds.Contains(u.Id))
            .ToListAsync(ct);
    }
}
