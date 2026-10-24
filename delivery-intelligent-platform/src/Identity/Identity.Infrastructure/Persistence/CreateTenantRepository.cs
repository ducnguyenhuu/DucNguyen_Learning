using Identity.Application.Abstractions;
using Identity.Domain.Memberships;
using Identity.Domain.Tenants;

namespace Identity.Infrastructure.Persistence;

/// <summary>
/// <see cref="IdentityDbContext"/>-backed implementation of <see cref="ICreateTenantRepository"/>.
/// </summary>
/// <remarks>
/// Sets <see cref="IdentityDbContext.CurrentTenantId"/> to the new tenant's id before calling
/// <c>SaveChangesAsync</c> — <c>TenantSaveChangesInterceptor</c> (T027) unconditionally stamps
/// every <see cref="Domain.Abstractions.ITenantOwned"/> entity in the
/// <see cref="Microsoft.EntityFrameworkCore.EntityState.Added"/> state with the context's ambient
/// <see cref="IdentityDbContext.CurrentTenantId"/>, so without this the new
/// <see cref="Membership"/> would be stamped with the CLR default (all-zero) <see cref="TenantId"/>
/// instead of the tenant it actually belongs to.
/// </remarks>
public class CreateTenantRepository : ICreateTenantRepository
{
    private readonly IdentityDbContext _dbContext;

    public CreateTenantRepository(IdentityDbContext dbContext)
    {
        _dbContext = dbContext;
    }

    public async Task AddAsync(Tenant tenant, Membership administratorMembership, CancellationToken ct)
    {
        _dbContext.CurrentTenantId = tenant.Id;

        _dbContext.Tenants.Add(tenant);
        _dbContext.Memberships.Add(administratorMembership);

        await _dbContext.SaveChangesAsync(ct);
    }
}
