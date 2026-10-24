using Identity.Application.Abstractions;
using Identity.Domain.Auditing;

namespace Identity.Infrastructure.Persistence;

/// <summary>
/// <see cref="IdentityDbContext"/>-backed implementation of <see cref="IAuditWriter"/>.
/// </summary>
/// <remarks>
/// <para>
/// <see cref="RecordAsync"/> stages the <see cref="AuditEntry"/> into the change tracker
/// but does <b>not</b> call <c>SaveChangesAsync</c>. This follows the design settled in
/// <see cref="IAuditWriter"/>'s contract (research.md R5): the caller (a use case, in a later
/// task) is responsible for calling <c>SaveChangesAsync()</c> itself once on its own
/// <c>IdentityDbContext</c> instance, ensuring that both its own entity changes and this
/// staged audit entry are persisted atomically in a single transaction. This design avoids
/// nested transactions and keeps the unit of work under the caller's control.
/// </para>
/// <para>
/// <c>Add()</c> is synchronous in EF Core — it only changes the tracker state, not I/O —
/// so <see cref="RecordAsync"/> has nothing to actually await; returning <c>Task.CompletedTask</c>
/// is the correct implementation, not a shortcut.
/// </para>
/// </remarks>
public class AuditWriter : IAuditWriter
{
    private readonly IdentityDbContext _dbContext;

    public AuditWriter(IdentityDbContext dbContext)
    {
        _dbContext = dbContext;
    }

    public Task RecordAsync(AuditEntry entry, CancellationToken ct)
    {
        _dbContext.AuditEntries.Add(entry);
        return Task.CompletedTask;
    }

    /// <summary>
    /// Stages <paramref name="entry"/> the same way <see cref="RecordAsync"/> does, then calls
    /// <c>SaveChangesAsync</c> itself — for call sites (authorization refusals) that have no
    /// later use-case save in the same request to piggyback on. Any exception from
    /// <c>SaveChangesAsync</c> propagates unhandled.
    /// </summary>
    public async Task RecordAndSaveAsync(AuditEntry entry, CancellationToken ct)
    {
        _dbContext.AuditEntries.Add(entry);
        await _dbContext.SaveChangesAsync(ct);
    }
}
