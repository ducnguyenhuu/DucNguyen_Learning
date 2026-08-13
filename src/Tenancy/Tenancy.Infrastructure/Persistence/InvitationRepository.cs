using Microsoft.EntityFrameworkCore;
using Tenancy.Application.Abstractions;
using Tenancy.Domain.Abstractions;
using Tenancy.Domain.Invitations;
using Tenancy.Domain.Memberships;

namespace Tenancy.Infrastructure.Persistence;

/// <summary>
/// <see cref="TenancyDbContext"/>-backed implementation of <see cref="IInvitationRepository"/>
/// (T078), following <see cref="TenantRepository"/>/<see cref="MembershipRepository"/>'s
/// established style.
/// </summary>
public class InvitationRepository : IInvitationRepository
{
    private readonly TenancyDbContext _dbContext;

    public InvitationRepository(TenancyDbContext dbContext)
    {
        _dbContext = dbContext;
    }

    public Task<bool> IsActiveMemberAsync(EmailAddress email, CancellationToken ct)
    {
        // Both Memberships and Users are scoped/joined against the ambient CurrentTenantId:
        // Memberships is ITenantOwned (covered by the "TenantFilter" query filter), and the
        // join to Users (never tenant-owned) narrows to the email match. No IgnoreQueryFilters
        // needed here — this is exactly the ambient-scoping shape GetTenant/GetActiveMembersAsync
        // already rely on.
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
        await _dbContext.SaveChangesAsync(ct);
    }

    public Task<Invitation?> FindByTokenHashAsync(string tokenHashBase64, CancellationToken ct)
    {
        // IgnoreQueryFilters bypasses the tenant-scoping "TenantFilter" filter — mandated by this
        // method's own doc comment: the caller presents a bare token with no ambient tenant yet
        // (the third ADR-017 exception), and the exact-hash-match predicate below is narrow enough
        // (a SHA-256 hash, effectively unguessable and unique per invitation) that this bypass
        // leaks nothing beyond "does this exact token match a real invitation, and if so, which
        // tenant" — precisely what accepting an invitation requires the caller to learn.
        return _dbContext.Invitations
            .IgnoreQueryFilters()
            .SingleOrDefaultAsync(i => i.TokenHash == tokenHashBase64, ct);
    }

    public async Task SaveAcceptedAsync(Invitation invitation, Membership membership, CancellationToken ct)
    {
        // Mirrors CreateTenant's (T054) "set CurrentTenantId before the save that includes the
        // new aggregate, one SaveChangesAsync call" precedent for the same "no ambient tenant yet"
        // shape — without this, TenantSaveChangesInterceptor (T027) would stamp the new
        // Membership with the CLR default TenantId rather than the invitation's tenant.
        _dbContext.CurrentTenantId = invitation.TenantId;

        _dbContext.Memberships.Add(membership);
        await _dbContext.SaveChangesAsync(ct);
    }

    public async Task<IReadOnlyList<Invitation>> GetAllForCurrentTenantAsync(CancellationToken ct)
    {
        // No IgnoreQueryFilters here: the tenant-scoping global query filter on Invitation
        // (ITenantOwned) is exactly what's wanted — TenancyDbContext.CurrentTenantId has already
        // been resolved to the caller's tenant by upstream middleware (ADR-017), same reliance as
        // MembershipRepository.GetActiveMembersAsync.
        return await _dbContext.Invitations
            .Where(i => i.Status == InvitationStatus.Pending)
            .ToListAsync(ct);
    }

    public Task<Invitation?> GetByIdForCurrentTenantAsync(InvitationId id, CancellationToken ct)
    {
        // Ambient-scoped, same as GetAllForCurrentTenantAsync above: a mismatched tenant simply
        // never returns a row (rather than needing a separate not-found-vs-wrong-tenant check),
        // matching the interface's documented "both indistinguishable" contract.
        return _dbContext.Invitations.SingleOrDefaultAsync(i => i.Id == id, ct);
    }

    public Task SaveAsync(Invitation invitation, CancellationToken ct)
    {
        return _dbContext.SaveChangesAsync(ct);
    }
}
