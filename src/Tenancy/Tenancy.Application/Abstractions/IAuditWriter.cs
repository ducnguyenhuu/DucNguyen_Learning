using Tenancy.Domain.Auditing;

namespace Tenancy.Application.Abstractions;

/// <summary>
/// Port for staging <see cref="AuditEntry"/> instances into the change tracker so that the caller's
/// own <c>SaveChangesAsync</c> will persist them alongside its own entity changes.
/// </summary>
/// <remarks>
/// <para>
/// <see cref="RecordAsync"/> does <b>not</b> call <c>SaveChangesAsync</c> itself; it only stages
/// the entry. The caller is responsible for calling <c>SaveChangesAsync</c> on the same
/// <c>TenancyDbContext</c> instance where the entry was staged, ensuring that the audit record is
/// persisted atomically with the caller's own domain changes (e.g., membership removal, tenant
/// rename). This design avoids nested transactions and keeps the unit of work in the caller's hands.
/// </para>
/// </remarks>
public interface IAuditWriter
{
    /// <summary>
    /// Stages the <paramref name="entry"/> into the change tracker for persistence when the caller
    /// invokes <c>SaveChangesAsync</c> on its own <c>TenancyDbContext</c>.
    /// </summary>
    /// <param name="entry">The <see cref="AuditEntry"/> to stage; expected to have been constructed
    /// via <see cref="AuditEntry.Create"/>.</param>
    /// <param name="ct">Cancellation token.</param>
    Task RecordAsync(AuditEntry entry, CancellationToken ct);
}
