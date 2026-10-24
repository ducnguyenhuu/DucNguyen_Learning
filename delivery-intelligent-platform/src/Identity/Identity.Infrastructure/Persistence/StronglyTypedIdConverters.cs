using Microsoft.EntityFrameworkCore.Storage.ValueConversion;
using Identity.Domain.Abstractions;

namespace Identity.Infrastructure.Persistence;

/// <summary>
/// EF Core value converters for the project's strongly-typed ID structs (each a
/// <c>readonly record struct</c> wrapping a single <see cref="Guid"/>). EF Core does not map
/// these natively or infer a conversion by convention, so every strongly-typed ID needs one of
/// these registered — see <see cref="IdentityDbContext.ConfigureConventions"/>, where registering
/// them once via <c>Properties&lt;T&gt;()</c> applies to every property of that type across every
/// entity (primary keys and foreign-key-shaped properties alike), rather than repeating
/// per-property <c>HasConversion</c> calls in each entity's configuration.
/// </summary>
public sealed class TenantIdConverter : ValueConverter<TenantId, Guid>
{
    public TenantIdConverter()
        : base(id => id.Value, value => new TenantId(value))
    {
    }
}

/// <inheritdoc cref="TenantIdConverter"/>
public sealed class UserIdConverter : ValueConverter<UserId, Guid>
{
    public UserIdConverter()
        : base(id => id.Value, value => new UserId(value))
    {
    }
}

/// <inheritdoc cref="TenantIdConverter"/>
public sealed class MembershipIdConverter : ValueConverter<MembershipId, Guid>
{
    public MembershipIdConverter()
        : base(id => id.Value, value => new MembershipId(value))
    {
    }
}

/// <inheritdoc cref="TenantIdConverter"/>
public sealed class InvitationIdConverter : ValueConverter<InvitationId, Guid>
{
    public InvitationIdConverter()
        : base(id => id.Value, value => new InvitationId(value))
    {
    }
}

/// <inheritdoc cref="TenantIdConverter"/>
public sealed class AuditEntryIdConverter : ValueConverter<AuditEntryId, Guid>
{
    public AuditEntryIdConverter()
        : base(id => id.Value, value => new AuditEntryId(value))
    {
    }
}
