using Tenancy.Domain.Abstractions;

namespace Tenancy.Domain.Tenants;

/// <summary>
/// The tenant aggregate root. A tenant's <see cref="DisplayName"/> is required but,
/// unlike a slug or domain, is explicitly not globally unique.
/// </summary>
public class Tenant
{
    private Tenant(TenantId id, string displayName, TenantStatus status, TenantSettings settings)
    {
        Id = id;
        DisplayName = displayName;
        Status = status;
        Settings = settings;
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
    /// The tenant's owned settings.
    /// </summary>
    public TenantSettings Settings { get; }

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

        return new Tenant(TenantId.New(), displayName, TenantStatus.Active, new TenantSettings());
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
