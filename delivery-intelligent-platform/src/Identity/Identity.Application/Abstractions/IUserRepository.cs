using Identity.Domain.Abstractions;
using Identity.Domain.Users;

namespace Identity.Application.Abstractions;

/// <summary>
/// Repository port for <see cref="User"/> persistence, kept deliberately minimal (only the two
/// operations <see cref="Users.EnsureUserProvisioned"/> needs — no speculative CRUD surface).
/// </summary>
/// <remarks>
/// This is the first repository port in the codebase (T036). Application depends only on this
/// interface, never on <c>IdentityDbContext</c> directly; <c>Identity.Infrastructure</c> supplies
/// the concrete implementation, per plan.md's Structure Decision (line 110: "Application/Abstractions/
/// ... repository ports").
/// </remarks>
public interface IUserRepository
{
    /// <summary>
    /// Finds a <see cref="User"/> by their composite Entra identity <c>(EntraTenantId, EntraObjectId)</c>,
    /// or <c>null</c> if no such user exists yet.
    /// </summary>
    Task<User?> FindByEntraIdentityAsync(Guid entraTenantId, Guid entraObjectId, CancellationToken ct);

    /// <summary>
    /// Adds a new <see cref="User"/> and persists it immediately (implementations are expected to
    /// call <c>SaveChangesAsync</c>, not merely stage the addition — callers rely on this to
    /// observe unique-constraint violations synchronously for the get-or-create race pattern).
    /// </summary>
    Task AddAsync(User user, CancellationToken ct);

    /// <summary>
    /// Returns every <see cref="User"/> whose <see cref="User.Id"/> is in <paramref name="userIds"/>
    /// (T076, added for <c>ListMembers</c> to resolve each <c>Membership.UserId</c> to a display
    /// email — <see cref="User"/> carries no tenant scoping of its own, so this is not a
    /// tenant-scoped read; callers are expected to have already restricted <paramref name="userIds"/>
    /// to a specific tenant's memberships before calling this).
    /// </summary>
    Task<IReadOnlyList<User>> FindByIdsAsync(IReadOnlyCollection<UserId> userIds, CancellationToken ct);
}
