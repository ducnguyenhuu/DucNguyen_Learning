using System.Security.Claims;
using Microsoft.AspNetCore.Authorization;

namespace Identity.Api.Authorization;

/// <summary>
/// The API's default authorization policy (ADR-022): a request is authorized only if its token
/// carries the delegated scope <see cref="DelegatedScope"/> (a signed-in user) or the app role
/// <see cref="AutomationRole"/> (a named, federated application identity). Every other token is
/// refused, including one carrying a different app role.
/// </summary>
/// <remarks>
/// Authentication alone is not enough. Microsoft.Identity.Web accepts any token that carries a
/// scope or a role, so without this policy the first app role ever added to the API's app
/// registration would silently admit every application holding it as if it were a user.
/// An identity admitted here gets a member's powers and nothing more: tenant membership is still
/// resolved from the database for every tenant-scoped request.
/// </remarks>
public static class CallerAuthorizationPolicy
{
    public const string DelegatedScope = "access_as_user";

    public const string AutomationRole = "Tenancy.Automation.Member";

    public static AuthorizationPolicy Build() =>
        new AuthorizationPolicyBuilder()
            .RequireAuthenticatedUser()
            .RequireAssertion(context => IsAuthorized(context.User))
            .Build();

    public static bool IsAuthorized(ClaimsPrincipal user)
    {
        // `scp` is one space-separated claim; `roles` is one claim per role. Claim names are the
        // literal token names because inbound claim mapping is disabled in Program.cs.
        var hasScope = user.FindAll("scp")
            .SelectMany(claim => claim.Value.Split(' ', StringSplitOptions.RemoveEmptyEntries))
            .Contains(DelegatedScope, StringComparer.Ordinal);

        var hasRole = user.FindAll("roles")
            .Any(claim => string.Equals(claim.Value, AutomationRole, StringComparison.Ordinal));

        return hasScope || hasRole;
    }
}
