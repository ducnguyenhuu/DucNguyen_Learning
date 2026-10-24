using Identity.Application.Abstractions;
using Identity.Domain.Abstractions;
using Identity.Domain.Users;

namespace Identity.Application.Users;

/// <summary>
/// Just-in-time provisions a <see cref="User"/> on first authenticated request, keyed on the
/// composite Entra identity <c>(EntraTenantId, EntraObjectId)</c> (T036).
/// </summary>
/// <remarks>
/// Deliberate non-goal: if a <see cref="User"/> row already exists, its <see cref="User.Email"/>
/// is never updated here, even if the token's current email differs from the stored one — email
/// is display/invitation-matching only (research.md R2), and email-sync is a separate concern
/// not in this task's scope.
///
/// This class provisions the <see cref="User"/> row only. It is a distinct concern from
/// membership resolution (T035's middleware) — a JIT-provisioned user with no memberships yet
/// still correctly yields a 404 from T035's middleware for a candidate tenant they don't belong
/// to. Wiring this use case into the request pipeline (or a specific endpoint) is out of scope
/// for this task; see the accompanying report for where later tasks are expected to call it.
/// </remarks>
public class EnsureUserProvisioned
{
    private readonly IUserRepository _userRepository;

    public EnsureUserProvisioned(IUserRepository userRepository)
    {
        _userRepository = userRepository;
    }

    /// <summary>
    /// Returns the existing <see cref="User"/> for the given Entra identity, or creates and
    /// persists a new one if none exists yet.
    /// </summary>
    /// <remarks>
    /// Race-condition handling: two near-simultaneous first-requests from the same identity
    /// could both miss the initial "not found" check and both attempt to insert. The database's
    /// unique index on <c>(EntraTenantId, EntraObjectId)</c> (see <c>UserConfiguration</c>, T025)
    /// guarantees only one insert succeeds; the loser's <c>SaveChangesAsync</c> throws
    /// <see cref="ConcurrencyConflictException"/>. That exception is caught broadly here — rather
    /// than narrowed to a provider-specific unique-constraint-violation subtype/error code —
    /// because discriminating the exact violation reliably would require a real database
    /// connection to verify against, which isn't available in this task's verification
    /// environment (build + code review only, no integration test harness yet). The tradeoff: a
    /// `ConcurrencyConflictException` caused by something other than this unique index (e.g. an
    /// unrelated constraint or connectivity blip) would also be swallowed and re-queried here, which could mask a real
    /// failure as a spurious "not found after re-query" `null`-turned-exception. This is judged
    /// acceptable for now given the narrow surface of this method (a single insert of one new
    /// row with no other constraints), but should be revisited if/when the provider-specific
    /// unique-violation type is confirmed against a real SQL Server instance.
    /// </remarks>
    public async Task<User> ExecuteAsync(
        Guid entraTenantId,
        Guid entraObjectId,
        EmailAddress email,
        CancellationToken ct)
    {
        var existing = await _userRepository.FindByEntraIdentityAsync(entraTenantId, entraObjectId, ct);
        if (existing is not null)
        {
            return existing;
        }

        var newUser = User.Create(entraTenantId, entraObjectId, email);

        try
        {
            await _userRepository.AddAsync(newUser, ct);
            return newUser;
        }
        catch (ConcurrencyConflictException)
        {
            // Lost the get-or-create race: another request inserted first. Re-query and return
            // the now-existing row instead of letting the exception propagate as an unhandled 500.
            var raceWinner = await _userRepository.FindByEntraIdentityAsync(entraTenantId, entraObjectId, ct);
            if (raceWinner is null)
            {
                // The insert failed for a reason other than the unique-index race (e.g. a
                // transient DB error), and no row exists on re-query either. Rethrow rather than
                // returning null/throwing something unrelated to the original failure.
                throw;
            }

            return raceWinner;
        }
    }
}
