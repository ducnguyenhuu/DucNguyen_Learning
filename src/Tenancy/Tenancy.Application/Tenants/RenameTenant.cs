using Microsoft.Extensions.Logging;
using Tenancy.Application.Abstractions;
using Tenancy.Domain.Abstractions;
using Tenancy.Domain.Auditing;
using Tenancy.Domain.Tenants;

namespace Tenancy.Application.Tenants;

/// <summary>
/// Renames the <see cref="Tenant"/> the caller is currently scoped to, for
/// <c>PATCH /tenants/{tenantId}</c> (Administrator-only per the contract).
/// </summary>
/// <remarks>
/// <para>
/// <b>No role check here:</b> per ADR-017 step 5, "Role authorization is evaluated against that
/// membership, not against the token" — that check is a cross-cutting concern layered on top
/// (likely T058's endpoint or a filter), not this use case's job. This use case is pure business
/// logic: fetch, rename, save.
/// </para>
/// <para>
/// <b>No concurrency handling here either:</b> this does not implement <c>If-Match</c>/ETag
/// checking (that's T057/T058). EF Core's own optimistic concurrency, via
/// <see cref="Tenant.RowVersion"/> (T025), throws <c>DbUpdateConcurrencyException</c> naturally
/// if the row changed since it was loaded — this use case doesn't translate that into an HTTP
/// status code, that's the HTTP layer's job.
/// </para>
/// </remarks>
public class RenameTenant
{
    private readonly ITenantRepository _tenantRepository;
    private readonly IAuditWriter _auditWriter;
    private readonly IClock _clock;
    private readonly ILogger<RenameTenant> _logger;

    public RenameTenant(
        ITenantRepository tenantRepository,
        IAuditWriter auditWriter,
        IClock clock,
        ILogger<RenameTenant> logger)
    {
        _tenantRepository = tenantRepository;
        _auditWriter = auditWriter;
        _clock = clock;
        _logger = logger;
    }

    /// <summary>
    /// Renames the ambient tenant to <paramref name="newDisplayName"/> and persists the change.
    /// Returns the updated <see cref="Tenant"/>, or <c>null</c> if it could not be found (which
    /// would indicate a bug further upstream, not this use case's concern).
    /// </summary>
    /// <param name="newDisplayName">The new display name.</param>
    /// <param name="renamedByUserId">The id of the already-authorized caller performing the
    /// rename, for the audit log entry. Authorization (only an Administrator may rename) is not
    /// this use case's concern — same division of responsibility as this class's remarks.</param>
    /// <param name="ct">Cancellation token.</param>
    /// <exception cref="DomainException">
    /// Thrown by <see cref="Tenant.Rename"/> when <paramref name="newDisplayName"/> is null,
    /// empty, or whitespace.
    /// </exception>
    public async Task<Tenant?> ExecuteAsync(
        string newDisplayName, UserId renamedByUserId, CancellationToken ct)
    {
        var tenant = await _tenantRepository.GetCurrentAsync(ct);
        if (tenant is null)
        {
            return null;
        }

        var oldDisplayName = tenant.DisplayName;

        tenant.Rename(newDisplayName);

        var auditEntry = AuditEntry.Create(
            tenant.Id,
            renamedByUserId,
            "tenant.renamed",
            "Tenant",
            tenant.Id.Value.ToString(),
            _clock);

        // Staged into the same TenancyDbContext instance SaveAsync uses — only staged, not
        // saved, here. SaveAsync's own SaveChangesAsync below flushes the rename and this
        // staged entry together, atomically.
        await _auditWriter.RecordAsync(auditEntry, ct);
        await _tenantRepository.SaveAsync(tenant, ct);

        _logger.LogInformation(
            "Tenant {TenantId} renamed from {OldDisplayName} to {NewDisplayName}",
            tenant.Id,
            oldDisplayName,
            newDisplayName);

        return tenant;
    }
}
