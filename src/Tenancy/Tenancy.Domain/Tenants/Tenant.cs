using Tenancy.Domain.Abstractions;

namespace Tenancy.Domain.Tenants;

/// <summary>
/// The tenant aggregate root. A tenant's <see cref="DisplayName"/> is required but,
/// unlike a slug or domain, is explicitly not globally unique.
/// </summary>
public class Tenant
{
    private Tenant(TenantId id, string displayName, TenantStatus status)
    {
        Id = id;
        DisplayName = displayName;
        Status = status;
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
    /// <exception cref="DomainException">Thrown when <paramref name="displayName"/> is null, empty, or whitespace.</exception>
    public static Tenant Create(string displayName)
    {
        EnsureValidDisplayName(displayName);

        return new Tenant(TenantId.New(), displayName, TenantStatus.Active);
    }

    /// <summary>
    /// Renames the tenant.
    /// </summary>
    /// <param name="newDisplayName">The new display name. Required, but not globally unique.</param>
    /// <exception cref="DomainException">Thrown when <paramref name="newDisplayName"/> is null, empty, or whitespace.</exception>
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
    }
}
