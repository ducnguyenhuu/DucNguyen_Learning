using System.Security.Claims;
using System.Text.Encodings.Web;
using Microsoft.AspNetCore.Authentication;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

namespace Identity.IntegrationTests.Infrastructure;

/// <summary>
/// Tier 1 test authentication handler for integration tests. Header-driven
/// (<c>X-Test-Oid</c>, <c>X-Test-Tid</c>) so a single shared host (see
/// <c>ApiFactory</c>, T042) can authenticate different callers as different
/// identities without any shared mutable state, keeping tests parallel-safe.
/// </summary>
/// <remarks>
/// Registered under the <see cref="SchemeName"/> scheme by <c>ApiFactory</c>
/// (T042). This class intentionally has no reference from <c>Program.cs</c> —
/// production code must never depend on test infrastructure.
/// </remarks>
public sealed class TestAuthHandler : AuthenticationHandler<AuthenticationSchemeOptions>
{
    /// <summary>
    /// The authentication scheme name this handler is registered under.
    /// Consumers (T041, T047) must use this exact value when configuring
    /// <c>ApiFactory</c> or issuing authenticated test requests.
    /// </summary>
    public const string SchemeName = "TestScheme";

    public TestAuthHandler(
        IOptionsMonitor<AuthenticationSchemeOptions> options,
        ILoggerFactory logger,
        UrlEncoder encoder)
        : base(options, logger, encoder)
    {
    }

    protected override Task<AuthenticateResult> HandleAuthenticateAsync()
    {
        // No Authorization header at all: this scheme has nothing to say.
        // NoResult() (not Fail()) lets the pipeline fall through to a genuine
        // 401 for unauthenticated requests, instead of asserting a scheme
        // matched-but-failed. Returning Fail() here would make every "401
        // without a token" test pass even if production auth were broken —
        // the exact failure mode this handler exists to avoid.
        if (!Request.Headers.TryGetValue("Authorization", out var authHeader)
            || string.IsNullOrWhiteSpace(authHeader))
        {
            return Task.FromResult(AuthenticateResult.NoResult());
        }

        // An Authorization header was presented, so the caller is claiming
        // to authenticate against this scheme. Missing/malformed test
        // identity headers at this point are a genuine failure, not "no
        // opinion" — the caller asked to authenticate but didn't supply what
        // this test scheme requires.
        if (!Request.Headers.TryGetValue("X-Test-Oid", out var oidValues)
            || string.IsNullOrWhiteSpace(oidValues.ToString()))
        {
            return Task.FromResult(AuthenticateResult.Fail("Missing or empty X-Test-Oid header."));
        }

        if (!Request.Headers.TryGetValue("X-Test-Tid", out var tidValues)
            || string.IsNullOrWhiteSpace(tidValues.ToString()))
        {
            return Task.FromResult(AuthenticateResult.Fail("Missing or empty X-Test-Tid header."));
        }

        var oid = oidValues.ToString();
        var tid = tidValues.ToString();

        // Claim names are literal "oid" / "tid" to match T032's production
        // JwtBearer configuration (MapInboundClaims = false). Test handler
        // and production auth must agree on claim names — disagreement here
        // is the classic "tests green, production 403" bug.
        var claims = new List<Claim>
        {
            new("oid", oid),
            new("tid", tid),
        };

        // Token kind, mirroring what Entra issues (ADR-022). A signed-in user's token carries the
        // delegated scope, which is what every test gets unless it says otherwise; an application
        // identity's token carries app roles and no scope. X-Test-Scp and X-Test-Roles override
        // that for the tests that exercise the caller policy.
        var hasScpHeader = Request.Headers.TryGetValue("X-Test-Scp", out var scpValues)
            && !string.IsNullOrWhiteSpace(scpValues.ToString());
        var hasRolesHeader = Request.Headers.TryGetValue("X-Test-Roles", out var roleValues)
            && !string.IsNullOrWhiteSpace(roleValues.ToString());

        if (hasScpHeader)
        {
            claims.Add(new Claim("scp", scpValues.ToString()));
        }
        else if (!hasRolesHeader)
        {
            claims.Add(new Claim("scp", "access_as_user"));
        }

        if (hasRolesHeader)
        {
            foreach (var role in roleValues.ToString().Split(',', StringSplitOptions.RemoveEmptyEntries))
            {
                claims.Add(new Claim("roles", role.Trim()));
            }
        }

        // Claim name is literal "email" to match InvitationEndpoints.AcceptInvitationAsync's
        // (T078) claim lookup order ("email", then "preferred_username", then "upn"). Tests that
        // exercise the accept-invitation identity check (InviteAndManageMembersTests,
        // InvitationRefusalTests, UnscopedOperationTests) set X-Test-Email and need it to surface
        // as this claim — without it, every caller resolves to the "{oid}@unresolved.invalid"
        // fallback and the wrong-identity check either always fails (403) or only "passes"
        // wrong-identity assertions by accident.
        if (Request.Headers.TryGetValue("X-Test-Email", out var emailValues)
            && !string.IsNullOrWhiteSpace(emailValues.ToString()))
        {
            claims.Add(new Claim("email", emailValues.ToString()));
        }

        var identity = new ClaimsIdentity(claims, SchemeName);
        var principal = new ClaimsPrincipal(identity);
        var ticket = new AuthenticationTicket(principal, SchemeName);

        return Task.FromResult(AuthenticateResult.Success(ticket));
    }
}
