using Tenancy.Application.Abstractions;
using Tenancy.Domain.Auditing;

namespace Tenancy.Infrastructure.Persistence;

/// <summary>
/// <see cref="TenancyDbContext"/>-backed implementation of <see cref="IAuditWriter"/>.
/// </summary>
/// <remarks>
/// <para>
/// <see cref="RecordAsync"/> stages the <see cref="AuditEntry"/> into the change tracker
/// but does <b>not</b> call <c>SaveChangesAsync</c>. This follows the design settled in
/// <see cref="IAuditWriter"/>'s contract (research.md R5): the caller (a use case, in a later
/// task) is responsible for calling <c>SaveChangesAsync()</c> itself once on its own
/// <c>TenancyDbContext</c> instance, ensuring that both its own entity changes and this
/// staged audit entry are persisted atomically in a single transaction. This design avoids
/// nested transactions and keeps the unit of work under the caller's control, much like
/// how <see cref="CreateTenantRepository"/> adds entities to the tracker and leaves
/// <c>SaveChangesAsync</c> to its caller.
/// </para>
/// <para>
/// <c>Add()</c> is synchronous in EF Core — it only changes the tracker state, not I/O —
/// so <see cref="RecordAsync"/> has nothing to actually await; returning <c>Task.CompletedTask</c>
/// is the correct implementation, not a shortcut.
/// </para>
/// </remarks>
public class AuditWriter : IAuditWriter
{
    private readonly TenancyDbContext _dbContext;

    public AuditWriter(TenancyDbContext dbContext)
    {
        _dbContext = dbContext;
    }

    public Task RecordAsync(AuditEntry entry, CancellationToken ct)
    {
        _dbContext.AuditEntries.Add(entry);
        return Task.CompletedTask;
    }
}
