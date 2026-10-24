using Identity.Domain.Auditing;

namespace Identity.Application.Abstractions;

/// <summary>
/// Port for staging <see cref="AuditEntry"/> instances into the change tracker so that the caller's
/// own <c>SaveChangesAsync</c> will persist them alongside its own entity changes.
/// </summary>
/// <remarks>
/// <para>
/// <see cref="RecordAsync"/> does <b>not</b> call <c>SaveChangesAsync</c> itself; it only stages
/// the entry. The caller is responsible for calling <c>SaveChangesAsync</c> on the same
/// <c>IdentityDbContext</c> instance where the entry was staged, ensuring that the audit record is
/// persisted atomically with the caller's own domain changes (e.g., membership removal, role
/// change). This design avoids nested transactions and keeps the unit of work in the caller's hands.
/// </para>
/// </remarks>
public interface IAuditWriter
{
    /// <summary>
    /// Stages the <paramref name="entry"/> into the change tracker for persistence when the caller
    /// invokes <c>SaveChangesAsync</c> on its own <c>IdentityDbContext</c>.
    /// </summary>
    /// <param name="entry">The <see cref="AuditEntry"/> to stage; expected to have been constructed
    /// via <see cref="AuditEntry.Create"/>.</param>
    /// <param name="ct">Cancellation token.</param>
    /// <remarks>
    /// <b>Invariant every call site must satisfy:</b> only call this once the caller is certain
    /// the action being audited will not fail before the caller's own <c>SaveChangesAsync</c>
    /// runs. Concretely: no step between this call and that <c>SaveChangesAsync</c> may still
    /// throw or return a non-success result. Violating this is not merely "fragile" in the
    /// abstract — it has two distinct failure shapes, depending on what happens after the
    /// violation:
    /// <list type="bullet">
    /// <item>On an endpoint with no later save that runs regardless of outcome: a staged entry
    /// is silently dropped (never flushed) if the later step fails — the audited action didn't
    /// happen, so losing its own audit record is arguably correct, but this only holds by
    /// accident of the surrounding transaction/DbContext lifetime, not by anything this
    /// interface enforces.</item>
    /// <item>On an endpoint wrapped by something that saves unconditionally afterward (e.g. an
    /// idempotency filter that commits its own transaction once the handler returns, independent
    /// of whether the audited action itself succeeded) — a staged entry could be silently
    /// persisted for an action that did not actually happen.</item>
    /// </list>
    /// Prefer staging as the very last thing before the call that triggers the save, after every
    /// fallible step has already succeeded (see <c>ChangeMemberRole</c>,
    /// <c>RevokeInvitation</c>, <c>AcceptInvitation</c> for this shape). <c>RemoveMember</c>,
    /// <c>InviteMember</c> and <c>BootstrapAdministrator</c> currently stage before a call that is
    /// itself both the last fallible step and the one that saves (<c>RemoveMembershipAsync</c>,
    /// <c>AddAsync</c>, <c>TryAddFirstAdministratorAsync</c>) — reordering those specific call
    /// sites would require splitting that repository call into a separate "attempt" step and
    /// "save" step, which is a larger repository-contract change than staging order alone; all
    /// three are currently safe only because the underlying repository call rolls back its own
    /// transaction (or, for <c>RemoveMember</c> and <c>BootstrapAdministrator</c>, never reaches
    /// <c>SaveChangesAsync</c> at all) on the failure path, so the staged-but-unflushed entry
    /// never reaches the database. That safety is incidental to those methods' own transaction
    /// handling, not guaranteed by this interface — re-verify it explicitly if any of these call
    /// sites' repository implementation changes.
    /// </remarks>
    Task RecordAsync(AuditEntry entry, CancellationToken ct);

    /// <summary>
    /// Stages the <paramref name="entry"/> and immediately calls <c>SaveChangesAsync</c> on the
    /// same <c>IdentityDbContext</c>, persisting it on its own.
    /// </summary>
    /// <remarks>
    /// For call sites that have no later use-case save to piggyback on in the same request — e.g.
    /// an authorization refusal, which short-circuits the request before any use case runs — and
    /// therefore cannot rely on <see cref="RecordAsync"/>'s "stage only, caller saves" contract.
    /// Does not swallow save failures: if <c>SaveChangesAsync</c> throws, the exception propagates
    /// to the caller rather than being caught here, so a refusal whose audit trail failed to
    /// persist is never reported as if it had succeeded.
    /// </remarks>
    /// <param name="entry">The <see cref="AuditEntry"/> to stage and persist; expected to have
    /// been constructed via <see cref="AuditEntry.Create"/>.</param>
    /// <param name="ct">Cancellation token.</param>
    Task RecordAndSaveAsync(AuditEntry entry, CancellationToken ct);
}
