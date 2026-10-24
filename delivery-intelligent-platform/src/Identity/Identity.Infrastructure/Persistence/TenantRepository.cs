using Microsoft.EntityFrameworkCore;
using Identity.Application.Abstractions;
using Identity.Domain.Abstractions;
using Identity.Domain.Tenants;

namespace Identity.Infrastructure.Persistence;

/// <summary>
/// <see cref="IdentityDbContext"/>-backed implementation of <see cref="ITenantRepository"/>.
/// </summary>
public class TenantRepository : ITenantRepository
{
    private readonly IdentityDbContext _dbContext;

    public TenantRepository(IdentityDbContext dbContext)
    {
        _dbContext = dbContext;
    }

    public Task<Tenant?> GetCurrentAsync(CancellationToken ct)
    {
        // Tenant is not ITenantOwned (see ITenantRepository's remarks), so it is never covered
        // by IdentityDbContext's "TenantFilter" global query filter — this explicit predicate
        // against the ambient CurrentTenantId is the only thing scoping this read to the
        // resolved tenant. Without it, this would throw once more than one Tenant row exists.
        return _dbContext.Tenants.SingleOrDefaultAsync(t => t.Id == _dbContext.CurrentTenantId, ct);
    }

    public async Task<IReadOnlyList<Tenant>> GetManyByIdsAsync(IReadOnlyCollection<TenantId> tenantIds, CancellationToken ct)
    {
        var tenants = await _dbContext.Tenants
            .Where(t => tenantIds.Contains(t.Id))
            .ToListAsync(ct);

        return tenants;
    }

    public Task SaveAsync(Tenant tenant, CancellationToken ct)
    {
        return _dbContext.SaveChangesAsync(ct);
    }
}
