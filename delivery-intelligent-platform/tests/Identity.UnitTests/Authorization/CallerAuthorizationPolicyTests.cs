using System.Security.Claims;
using AwesomeAssertions;
using Identity.Api.Authorization;
using Xunit;

namespace Identity.UnitTests.Authorization;

/// <summary>
/// ADR-022: the API accepts exactly two kinds of caller — a user holding the delegated scope
/// <c>access_as_user</c>, or an application holding the app role <c>Tenancy.Automation.Member</c>
/// (a value defined on the Entra app registration, kept under its old name by ADR-025).
/// <see cref="CallerAuthorizationPolicy.IsDelegatedUser"/> narrows that to the first kind for
/// <c>POST /members/bootstrap</c>, which an application identity must never call (ADR-025).
/// </summary>
public class CallerAuthorizationPolicyTests
{
    private static ClaimsPrincipal Token(params Claim[] claims) =>
        new(new ClaimsIdentity(claims, authenticationType: "Bearer"));

    [Fact]
    public void DelegatedScope_IsAccepted()
    {
        CallerAuthorizationPolicy.IsAuthorized(Token(new Claim("scp", "access_as_user"))).Should().BeTrue();
    }

    [Fact]
    public void DelegatedScope_AmongOtherScopes_IsAccepted()
    {
        CallerAuthorizationPolicy.IsAuthorized(Token(new Claim("scp", "profile access_as_user email"))).Should().BeTrue();
    }

    [Fact]
    public void AutomationRole_IsAccepted()
    {
        CallerAuthorizationPolicy.IsAuthorized(Token(new Claim("roles", "Tenancy.Automation.Member"))).Should().BeTrue();
    }

    [Fact]
    public void AutomationRole_AmongOtherRoles_IsAccepted()
    {
        var token = Token(new Claim("roles", "Some.Other.Role"), new Claim("roles", "Tenancy.Automation.Member"));

        CallerAuthorizationPolicy.IsAuthorized(token).Should().BeTrue();
    }

    [Fact]
    public void TokenWithNeitherScopeNorRole_IsRejected()
    {
        CallerAuthorizationPolicy.IsAuthorized(Token(new Claim("oid", Guid.NewGuid().ToString()))).Should().BeFalse();
    }

    [Fact]
    public void TokenWithADifferentRole_IsRejected()
    {
        CallerAuthorizationPolicy.IsAuthorized(Token(new Claim("roles", "Some.Other.Role"))).Should().BeFalse();
    }

    [Fact]
    public void TokenWithAnUnrelatedScope_IsRejected()
    {
        CallerAuthorizationPolicy.IsAuthorized(Token(new Claim("scp", "user_impersonation"))).Should().BeFalse();
    }

    [Fact]
    public void ScopeNameThatOnlyContainsTheRequiredOne_IsRejected()
    {
        CallerAuthorizationPolicy.IsAuthorized(Token(new Claim("scp", "access_as_user_admin"))).Should().BeFalse();
    }

    [Fact]
    public void AutomationRoleNameInTheScopeClaim_IsRejected()
    {
        // Scopes and roles are different claims; a value in the wrong one must not count.
        CallerAuthorizationPolicy.IsAuthorized(Token(new Claim("scp", "Tenancy.Automation.Member"))).Should().BeFalse();
    }

    [Fact]
    public void IsDelegatedUser_WithDelegatedScope_IsTrue()
    {
        CallerAuthorizationPolicy.IsDelegatedUser(Token(new Claim("scp", "profile access_as_user"))).Should().BeTrue();
    }

    [Fact]
    public void IsDelegatedUser_WithOnlyTheAutomationRole_IsFalse()
    {
        // The application identity passes the default policy, but must never bootstrap the first
        // administrator.
        var token = Token(new Claim("roles", "Tenancy.Automation.Member"));

        CallerAuthorizationPolicy.IsAuthorized(token).Should().BeTrue();
        CallerAuthorizationPolicy.IsDelegatedUser(token).Should().BeFalse();
    }
}
