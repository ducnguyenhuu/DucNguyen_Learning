using Tenancy.Domain.Abstractions;

namespace Tenancy.Domain.Tenants;

/// <summary>
/// The tenant aggregate root. A tenant's <see cref="DisplayName"/> is required but,
/// unlike a slug or domain, is explicitly not globally unique.
/// </summary>
public class Tenant
{
    /// <summary>
    /// Upper bound on <see cref="DisplayName"/>'s length. The domain owns this rule and
    /// <c>TenantConfiguration</c> derives its column length from it, rather than the two
    /// declaring the limit independently — see ADR-021, which records the drift this closes:
    /// the database column enforced 200 while the domain checked only null/whitespace, so an
    /// over-long name reached SQL Server and surfaced as a 500 instead of a 400.
    /// </summary>
    public const int DisplayNameMaxLength = 200;

    private Tenant(TenantId id, string displayName, TenantStatus status)
    {
        Id = id;
        DisplayName = displayName;
        Status = status;
        CreatedAtUtc = DateTimeOffset.UtcNow;
    }

    /// <summary>
    /// The unique identifier of the tenant.
    /// </summary>
    public TenantId Id { get; }

    /// <summary>
    /// The human-readable name of the tenant. Required, but not globally unique.
    /// </summary>
    public string DisplayName { get; private set; }

    /// <summary>
    /// The lifecycle status of the tenant.
    /// </summary>
    public TenantStatus Status { get; private set; }

    /// <summary>
    /// UTC instant this tenant was created, per <c>contracts/openapi.yaml</c>'s <c>Tenant</c>
    /// schema (<c>createdAtUtc</c> is a required response field). Set once, at construction, and
    /// never changed. EF Core persists this rather than deriving it, so it survives across reads.
    /// </summary>
    public DateTimeOffset CreatedAtUtc { get; private set; }

    /// <summary>
    /// The tenant's owned settings. Not accepted through the constructor: EF Core cannot bind
    /// constructor parameters to owned/complex reference-type properties (see
    /// <c>TenantConfiguration</c>), and the settings object currently carries no state of its
    /// own anyway, so a stable default instance is created here instead.
    /// </summary>
    public TenantSettings Settings { get; } = new TenantSettings();

    /// <summary>
    /// Concurrency token maintained by the database (SQL Server <c>rowversion</c>). Never set by
    /// application code — EF Core populates it on read/write.
    /// </summary>
    public byte[] RowVersion { get; private set; } = [];

    /// <summary>
    /// Creates a new, active tenant with the given display name.
    /// </summary>
    /// <param name="displayName">The tenant's display name. Required, but not globally unique.</param>
    /// <exception cref="DomainException">Thrown when <paramref name="displayName"/> is null, empty,
    /// whitespace, or longer than <see cref="DisplayNameMaxLength"/>.</exception>
    public static Tenant Create(string displayName)
    {
        EnsureValidDisplayName(displayName);

        return new Tenant(TenantId.New(), displayName, TenantStatus.Active);
    }

    /// <summary>
    /// Renames the tenant.
    /// </summary>
    /// <param name="newDisplayName">The new display name. Required, but not globally unique.</param>
    /// <exception cref="DomainException">Thrown when <paramref name="newDisplayName"/> is null, empty,
    /// whitespace, or longer than <see cref="DisplayNameMaxLength"/>.</exception>
    public void Rename(string newDisplayName)
    {
        EnsureValidDisplayName(newDisplayName);

        DisplayName = newDisplayName;
    }

    private static void EnsureValidDisplayName(string displayName)
    {
        if (string.IsNullOrWhiteSpace(displayName))
        {
            throw new DomainException("Tenant display name is required.");
        }

        if (displayName.Length > DisplayNameMaxLength)
        {
            throw new DomainException(
                $"Tenant display name must be {DisplayNameMaxLength} characters or fewer.");
        }
    }
}
