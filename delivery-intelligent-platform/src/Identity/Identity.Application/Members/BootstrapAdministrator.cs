using Microsoft.Extensions.Logging;
using Identity.Application.Abstractions;
using Identity.Domain.Abstractions;
using Identity.Domain.Auditing;
using Identity.Domain.Memberships;

namespace Identity.Application.Members;

/// <summary>
/// Makes the caller the organization's first <see cref="Role.Administrator"/>, for
/// <c>POST /members/bootstrap</c> (ADR-025). Succeeds only while the organization has no active
/// membership at all; once anyone is a member, new members join only by invitation.
/// </summary>
/// <remarks>
/// <para>
/// This replaces tenant creation (FR-005, as reinterpreted by ADR-025) as the way the first
/// administrator comes to exist. "Only delegated user tokens" is the endpoint's check, not this
/// use case's: an application identity never reaches here.
/// </para>
/// <para>
/// <b>Audit staging:</b> the audit entry is staged into the shared <c>IdentityDbContext</c> before
/// <see cref="IMembershipRepository.TryAddFirstAdministratorAsync"/> runs, so its single save
/// flushes both together. On the conflict path that method returns before saving, and nothing
/// else in the request saves afterwards, so the staged entry is never written — the same shape
/// <c>RemoveMember</c> relies on for its own refused path.
/// </para>
/// </remarks>
public class BootstrapAdministrator
{
    private readonly IMembershipRepository _membershipRepository;
    private readonly IAuditWriter _auditWriter;
    private readonly IClock _clock;
    private readonly ILogger<BootstrapAdministrator> _logger;

    public BootstrapAdministrator(
        IMembershipRepository membershipRepository,
        IAuditWriter auditWriter,
        IClock clock,
        ILogger<BootstrapAdministrator> logger)
    {
        _membershipRepository = membershipRepository;
        _auditWriter = auditWriter;
        _clock = clock;
        _logger = logger;
    }

    /// <summary>
    /// Grants <paramref name="callerUserId"/> an <see cref="Role.Administrator"/> membership if the
    /// organization has no active members yet.
    /// </summary>
    public async Task<BootstrapAdministratorResult> ExecuteAsync(UserId callerUserId, CancellationToken ct)
    {
        var membership = Membership.Create(callerUserId, Role.Administrator);

        var auditEntry = AuditEntry.Create(
            callerUserId,
            "membership.bootstrapped",
            "Membership",
            callerUserId.Value.ToString(),
            _clock);

        await _auditWriter.RecordAsync(auditEntry, ct);

        if (!await _membershipRepository.TryAddFirstAdministratorAsync(membership, ct))
        {
            _logger.LogInformation(
                "Bootstrap refused for user {UserId}: the organization already has members",
                callerUserId);

            return BootstrapAdministratorResult.Conflict();
        }

        _logger.LogInformation("User {UserId} bootstrapped as the first administrator", callerUserId);

        return BootstrapAdministratorResult.Success(membership);
    }
}

/// <summary>
/// The outcome of <see cref="BootstrapAdministrator.ExecuteAsync"/>.
/// </summary>
public record BootstrapAdministratorResult(BootstrapAdministratorResultKind Kind, Membership? Membership = null)
{
    public static BootstrapAdministratorResult Success(Membership membership) =>
        new(BootstrapAdministratorResultKind.Success, membership);

    public static BootstrapAdministratorResult Conflict() => new(BootstrapAdministratorResultKind.Conflict);
}

/// <summary>
/// The discriminant of <see cref="BootstrapAdministratorResult"/>.
/// </summary>
public enum BootstrapAdministratorResultKind
{
    /// <summary>The caller is now the first administrator. Maps to <c>201 Created</c>.</summary>
    Success,

    /// <summary>The organization already has members. Maps to <c>409 Conflict</c>.</summary>
    Conflict,
}
