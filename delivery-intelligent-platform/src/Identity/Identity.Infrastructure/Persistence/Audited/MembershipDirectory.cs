using Microsoft.EntityFrameworkCore;
using Identity.Application.Abstractions;
using Identity.Domain.Abstractions;
using Identity.Domain.Memberships;

namespace Identity.Infrastructure.Persistence.Audited;

/// <summary>
/// <see cref="IdentityDbContext"/>-backed implementation of <see cref="IMembershipDirectory"/>.
/// </summary>
/// <remarks>
/// This is the <b>only</b> sanctioned cross-tenant bypass in the codebase (per ADR-017), used
/// exclusively by <c>GET /tenants</c> to list the calling user's own memberships across every
/// tenant they belong to. Its query bypasses <b>only</b> the named <c>"TenantFilter"</c> global
/// query filter applied in <see cref="IdentityDbContext.OnModelCreating"/> — never a bare,
/// unscoped <c>IgnoreQueryFilters()</c>, which would also disable any other filter later added
/// to <see cref="Membership"/> and has nothing to do with tenancy. The bypass is paired, in the
/// same query, with a mandatory <c>UserId == userId</c> predicate: there is no code path here
/// that returns memberships without being scoped to a specific caller. Any other code that
/// believes it needs cross-tenant visibility is a design defect, not grounds for a second
/// bypass helper — extend or reuse this one instead of copying its pattern.
/// </remarks>
public class MembershipDirectory : IMembershipDirectory
{
    private readonly IdentityDbContext _dbContext;

    public MembershipDirectory(IdentityDbContext dbContext)
    {
        _dbContext = dbContext;
    }

    public Task<IReadOnlyList<Membership>> GetMembershipsForUserAsync(UserId userId, CancellationToken ct)
    {
        return GetMembershipsForUserCoreAsync(userId, ct);
    }

    private async Task<IReadOnlyList<Membership>> GetMembershipsForUserCoreAsync(UserId userId, CancellationToken ct)
    {
        var memberships = await _dbContext.Set<Membership>()
            .IgnoreQueryFilters(["TenantFilter"])
            .Where(m => m.UserId == userId && m.Status == MembershipStatus.Active)
            .ToListAsync(ct);

        return memberships;
    }
}
