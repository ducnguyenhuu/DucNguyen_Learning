using Microsoft.EntityFrameworkCore;
using Tenancy.Application.Abstractions;
using Tenancy.Domain.Abstractions;
using Tenancy.Domain.Tenants;

namespace Tenancy.Infrastructure.Persistence;

/// <summary>
/// <see cref="TenancyDbContext"/>-backed implementation of <see cref="ITenantRepository"/>.
/// </summary>
public class TenantRepository : ITenantRepository
{
    private readonly TenancyDbContext _dbContext;

    public TenantRepository(TenancyDbContext dbContext)
    {
        _dbContext = dbContext;
    }

    public Task<Tenant?> GetCurrentAsync(CancellationToken ct)
    {
        // Tenant is not ITenantOwned (see ITenantRepository's remarks), so it is never covered
        // by TenancyDbContext's "TenantFilter" global query filter — this explicit predicate
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
