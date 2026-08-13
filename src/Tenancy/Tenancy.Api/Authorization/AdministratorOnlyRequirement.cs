using Microsoft.AspNetCore.Authorization;

namespace Tenancy.Api.Authorization;

/// <summary>
/// Authorization requirement satisfied only when the caller's <see cref="Tenancy.Domain.Abstractions.Role"/>
/// in the current tenant — as resolved by <c>TenantContextResolutionMiddleware</c> (T035) from the
/// real <c>Membership</c> row, never from a token claim (ADR-017 step 5) — is
/// <see cref="Tenancy.Domain.Abstractions.Role.Administrator"/>.
/// </summary>
/// <remarks>
/// This is deliberately a single fixed-role requirement, not a general minimum-role hierarchy.
/// Per Assumption 5, Member and Reader are behaviorally identical everywhere in this codebase
/// today, so the only distinction any operation actually needs is Administrator-vs-not. Building
/// a general <c>RequireRoleRequirement(Role minimumRole)</c> mechanism with an implied
/// Administrator &gt; Member &gt; Reader ordering would be speculative machinery for a
/// distinction nobody currently draws (Principle X: don't build for an anticipated need). If a
/// genuine second tier is ever needed, it should be added then, informed by the real requirement,
/// rather than guessed at now.
/// </remarks>
public sealed class AdministratorOnlyRequirement : IAuthorizationRequirement
{
}
