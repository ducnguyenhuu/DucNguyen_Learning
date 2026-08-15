using Tenancy.Domain.Abstractions;

namespace Tenancy.Application.Invitations;

/// <summary>
/// The "delivery" seam for a pending invitation's raw token (Assumption 8): for this slice a
/// development-time mechanism (logged or captured locally) is acceptable — the specification
/// requires only that a pending invitation is recorded and acceptable, not that real email is
/// sent. <see cref="InviteMember"/> (T071) calls this after the invitation is successfully
/// persisted, so a later slice can swap in a real email-sending implementation behind this same
/// port without touching <see cref="InviteMember"/> itself.
/// </summary>
public interface IInvitationDeliverySink
{
    /// <summary>
    /// "Delivers" the invitation to <paramref name="recipient"/>. Implementations receive the raw,
    /// unhashed <paramref name="rawToken"/> because delivery conceptually requires handing the
    /// invitee the real token — but per FR-025's established templated-logging discipline (T059),
    /// no implementation may ever log <paramref name="rawToken"/> itself; it is the literal
    /// unhashed credential, not merely a hash of one.
    /// </summary>
    Task DeliverAsync(EmailAddress recipient, string rawToken, CancellationToken ct);
}
