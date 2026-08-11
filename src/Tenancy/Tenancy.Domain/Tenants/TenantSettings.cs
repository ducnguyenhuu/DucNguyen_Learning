namespace Tenancy.Domain.Tenants;

/// <summary>
/// Owned settings for a <see cref="Tenant"/>. Intentionally minimal for now; grows as
/// tenant-level configuration needs emerge. Kept as a reference type so <see cref="Tenant"/>
/// can hold a stable, non-null instance from creation.
/// </summary>
public class TenantSettings
{
}
