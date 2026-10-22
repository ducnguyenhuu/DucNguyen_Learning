using Microsoft.EntityFrameworkCore;
using Tenancy.Application.Abstractions;
using Tenancy.Domain.Abstractions;
using Tenancy.Domain.Users;

namespace Tenancy.Infrastructure.Persistence;

/// <summary>
/// <see cref="TenancyDbContext"/>-backed implementation of <see cref="IUserRepository"/>.
/// </summary>
public class UserRepository : IUserRepository
{
    private readonly TenancyDbContext _dbContext;

    public UserRepository(TenancyDbContext dbContext)
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
