using Microsoft.Extensions.Logging;
using Tenancy.Application.Abstractions;
using Tenancy.Domain.Abstractions;
using Tenancy.Domain.Memberships;
using Tenancy.Domain.Tenants;

namespace Tenancy.Application.Tenants;

/// <summary>
/// Creates a new <see cref="Tenant"/> together with the creator's <see cref="Role.Administrator"/>
/// <see cref="Membership"/>, in one transaction (FR-005). This is the first application-layer use
/// case in the whole slice that writes two aggregates atomically.
/// </summary>
/// <remarks>
/// <para>
/// <b>Ordering:</b> <see cref="Tenant.Create"/> generates the new <see cref="TenantId"/>
/// client-side (via <c>TenantId.New()</c>, a <c>Guid.CreateVersion7()</c>-backed strongly-typed
/// ID — never a database <c>IDENTITY</c>/<c>SEQUENCE</c>), so <c>tenant.Id</c> is available
/// immediately after <see cref="Tenant.Create"/> returns, before anything is persisted. That lets
/// <see cref="Membership.Create"/> be called right after, with the new tenant's id, and both
/// aggregates handed to <see cref="ICreateTenantRepository.AddAsync"/> in a single call — no
/// two-phase save needed.
/// </para>
/// <para>
/// <b>Transaction:</b> a single <c>DbContext.SaveChangesAsync()</c> call already wraps every
/// pending insert in one implicit database transaction (EF Core's documented behavior for one
/// context, one <c>SaveChanges</c> call) — both the new <see cref="Tenant"/> and the new
/// <see cref="Membership"/> are added to the same context and saved together in
/// <c>ICreateTenantRepository</c>'s single <c>SaveChangesAsync</c> call, so no explicit
/// <c>BeginTransactionAsync</c> is needed here.
/// </para>
/// <para>
/// <b>CurrentTenantId:</b> <c>TenantSaveChangesInterceptor</c> (T027) stamps every
/// <see cref="Domain.Abstractions.ITenantOwned"/> entity in the <see cref="EntityState.Added"/>
/// state with <c>TenancyDbContext.CurrentTenantId</c> unconditionally on save — including
/// overwriting whatever <see cref="Membership.TenantId"/> was constructed with. Before this use
/// case existed, nothing in the request pipeline had a reason to set <c>CurrentTenantId</c> to a
/// tenant that doesn't exist in the database yet, so it is the CLR default <c>TenantId</c> value
/// at this point. <c>ICreateTenantRepository</c>'s implementation (<c>CreateTenantRepository</c>,
/// infrastructure-side) is therefore responsible for setting
/// <c>TenancyDbContext.CurrentTenantId = tenant.Id</c> before calling <c>SaveChangesAsync</c> —
/// if it didn't, the interceptor would stamp the new <see cref="Membership"/> with the default
/// (all-zero) <see cref="TenantId"/> instead of the real one, silently corrupting the row.
/// </para>
/// </remarks>
public class CreateTenant
{
    private readonly ICreateTenantRepository _createTenantRepository;
    private readonly ILogger<CreateTenant> _logger;

    public CreateTenant(ICreateTenantRepository createTenantRepository, ILogger<CreateTenant> logger)
    {
        _createTenantRepository = createTenantRepository;
        _logger = logger;
    }

    /// <summary>
    /// Creates a new tenant named <paramref name="displayName"/> and grants
    /// <paramref name="creatorUserId"/> an <see cref="Role.Administrator"/> membership on it,
    /// persisting both atomically. Returns the created <see cref="Tenant"/>.
    /// </summary>
    /// <param name="displayName">
    /// The new tenant's display name. Validated by <see cref="Tenant.Create"/> (throws
    /// <see cref="DomainException"/> on null/empty/whitespace) — not re-validated here.
    /// </param>
    /// <param name="creatorUserId">
    /// The id of the already-provisioned <see cref="Domain.Users.User"/> who is creating the
    /// tenant. Resolving/provisioning that user (e.g. via <c>EnsureUserProvisioned</c>, T036) is
    /// the caller's responsibility, not this use case's.
    /// </param>
    public async Task<Tenant> ExecuteAsync(string displayName, UserId creatorUserId, CancellationToken ct)
    {
        var tenant = Tenant.Create(displayName);
        var administratorMembership = Membership.Create(tenant.Id, creatorUserId, Role.Administrator);

        await _createTenantRepository.AddAsync(tenant, administratorMembership, ct);

        _logger.LogInformation(
            "Tenant {TenantId} created by user {UserId}",
            tenant.Id,
            creatorUserId);

        return tenant;
    }
}
