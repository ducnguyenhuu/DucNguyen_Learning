using Microsoft.EntityFrameworkCore;
using Tenancy.Application.Abstractions;
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
        await _dbContext.SaveChangesAsync(ct);
    }
}
