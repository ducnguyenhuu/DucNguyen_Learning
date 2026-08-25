using Tenancy.Domain.Abstractions;

namespace Tenancy.Domain.Auditing;

/// <summary>
/// An immutable record of a single action taken against a resource, captured for later review.
/// <see cref="TenantId"/> and <see cref="ActorUserId"/> may both be <c>null</c> — this is the
/// unauthenticated-refusal case (e.g. a rejected request with no resolved tenant context), not an
/// error.
/// </summary>
public class AuditEntry
{
    private AuditEntry(
        AuditEntryId id,
        TenantId? tenantId,
        UserId? actorUserId,
        string action,
        string resourceType,
        string resourceId,
        DateTimeOffset occurredAtUtc)
    {
        Id = id;
        TenantId = tenantId;
        ActorUserId = actorUserId;
        Action = action;
        ResourceType = resourceType;
        ResourceId = resourceId;
        OccurredAtUtc = occurredAtUtc;
    }

    /// <summary>
    /// The unique identifier of the audit entry.
    /// </summary>
    public AuditEntryId Id { get; }

    /// <summary>
    /// The ID of the tenant the action occurred within, or <c>null</c> if no tenant context had
    /// been resolved (e.g. an unauthenticated-refusal case).
    /// </summary>
    public TenantId? TenantId { get; }

    /// <summary>
    /// The ID of the user who performed the action, or <c>null</c> if no user context had been
    /// resolved (e.g. an unauthenticated-refusal case).
    /// </summary>
    public UserId? ActorUserId { get; }

    /// <summary>
    /// The action that was performed (e.g. <c>"membership.removed"</c>).
    /// </summary>
    public string Action { get; }

    /// <summary>
    /// The type of resource the action was performed against (e.g. <c>"Membership"</c>).
    /// </summary>
    public string ResourceType { get; }

    /// <summary>
    /// The identifier of the resource the action was performed against.
    /// </summary>
    public string ResourceId { get; }

    /// <summary>
    /// The timestamp at which the action occurred, read from the <see cref="IClock"/> supplied to
    /// <see cref="Create"/>.
    /// </summary>
    public DateTimeOffset OccurredAtUtc { get; }

    /// <summary>
    /// Creates a new audit entry recording that <paramref name="action"/> was performed against
    /// the resource identified by <paramref name="resourceType"/>/<paramref name="resourceId"/>,
    /// with <see cref="OccurredAtUtc"/> read from <paramref name="clock"/>.
    /// </summary>
    /// <param name="tenantId">The tenant the action occurred within, or <c>null</c> if no tenant
    /// context had been resolved.</param>
    /// <param name="actorUserId">The user who performed the action, or <c>null</c> if no user
    /// context had been resolved.</param>
    /// <param name="action">The action performed. Required.</param>
    /// <param name="resourceType">The type of resource acted upon. Required.</param>
    /// <param name="resourceId">The identifier of the resource acted upon. Required.</param>
    /// <param name="clock">The clock used to read the current time, injected so the entity — not
    /// the caller — is responsible for reading "now".</param>
    /// <exception cref="DomainException">Thrown if <paramref name="action"/>,
    /// <paramref name="resourceType"/>, or <paramref name="resourceId"/> is null, empty, or
    /// whitespace.</exception>
    public static AuditEntry Create(
        TenantId? tenantId,
        UserId? actorUserId,
        string action,
        string resourceType,
        string resourceId,
        IClock clock)
    {
        if (string.IsNullOrWhiteSpace(action))
        {
            throw new DomainException("Action is required.");
        }

        if (string.IsNullOrWhiteSpace(resourceType))
        {
            throw new DomainException("ResourceType is required.");
        }

        if (string.IsNullOrWhiteSpace(resourceId))
        {
            throw new DomainException("ResourceId is required.");
        }

        return new AuditEntry(
            AuditEntryId.New(),
            tenantId,
            actorUserId,
            action,
            resourceType,
            resourceId,
            clock.UtcNow);
    }
}
