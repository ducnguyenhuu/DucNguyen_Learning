using System.Net;
using System.Net.Http.Json;
using AwesomeAssertions;
using Identity.Domain.Abstractions;
using Identity.IntegrationTests.Infrastructure;
using Xunit;

namespace Identity.IntegrationTests.Authorization;

/// <summary>
/// ADR-022 under ADR-025: an application identity holding <c>Tenancy.Automation.Member</c> passes
/// the default caller policy, but that app role grants nothing by itself. What it may do is
/// decided by its membership, exactly like a signed-in user's — and it can never bootstrap the
/// first administrator. A token with neither the user scope nor that role is refused outright.
/// </summary>
/// <remarks>
/// The app role keeps its historical <c>Tenancy.</c> prefix: it is registered in Entra, outside
/// this repository, and ADR-025 deliberately leaves it unrenamed.
/// </remarks>
public sealed class AutomationIdentityTests : IdentityIntegrationTestBase
{
    private const string AutomationRole = "Tenancy.Automation.Member";

    public AutomationIdentityTests(SqlServerFixture sqlServerFixture, ApiFactory factory)
        : base(sqlServerFixture, factory)
    {
    }

    /// <summary>
    /// An automation identity with no membership is refused on a member-only route with the same
    /// 403, byte for byte, as a signed-in user with no membership — the app role is not a
    /// back door past membership resolution.
    /// </summary>
    [Fact]
    public async Task AutomationIdentity_WithoutMembership_IsRefusedExactlyLikeANonMemberUser()
    {
        await Factory.SeedMemberAsync(Role.Administrator);

        using var automation = Factory.CreateClientForStranger();
        automation.DefaultRequestHeaders.Add("X-Test-Roles", AutomationRole);
        using var user = Factory.CreateClientForStranger();

        var automationResponse = await automation.GetAsync("/members", TestContext.Current.CancellationToken);
        var userResponse = await user.GetAsync("/members", TestContext.Current.CancellationToken);

        automationResponse.StatusCode.Should().Be(HttpStatusCode.Forbidden);
        userResponse.StatusCode.Should().Be(HttpStatusCode.Forbidden);

        var automationBody = await automationResponse.Content.ReadAsStringAsync(TestContext.Current.CancellationToken);
        var userBody = await userResponse.Content.ReadAsStringAsync(TestContext.Current.CancellationToken);
        automationBody.Should().Be(userBody);
    }

    /// <summary>
    /// An automation identity that has been made a Member gets a Member's powers and no more:
    /// <c>GET /me</c> reports the membership role, and administrator-only routes still refuse it.
    /// The token's app role never stands in for an organization role.
    /// </summary>
    [Fact]
    public async Task AutomationIdentity_WithMemberMembership_HasMemberPowersOnly()
    {
        await Factory.SeedMemberAsync(Role.Administrator);
        var automationMember = await Factory.SeedMemberAsync(Role.Member);

        using var automation = Factory.CreateClientFor(automationMember);
        automation.DefaultRequestHeaders.Add("X-Test-Roles", AutomationRole);

        var me = await automation.GetAsync("/me", TestContext.Current.CancellationToken);
        me.StatusCode.Should().Be(HttpStatusCode.OK);
        var meBody = await me.Content.ReadFromJsonAsync<MeResponse>(TestContext.Current.CancellationToken);
        meBody!.Role.Should().Be("Member");

        var members = await automation.GetAsync("/members", TestContext.Current.CancellationToken);
        var invitations = await automation.GetAsync("/invitations", TestContext.Current.CancellationToken);

        members.StatusCode.Should().Be(HttpStatusCode.Forbidden);
        invitations.StatusCode.Should().Be(HttpStatusCode.Forbidden);
    }

    /// <summary>
    /// An automation identity can never become the first administrator, even of an empty
    /// organization: <c>POST /members/bootstrap</c> requires a delegated user token (ADR-025).
    /// </summary>
    [Fact]
    public async Task AutomationIdentity_CannotBootstrap_EvenIntoAnEmptyOrganization()
    {
        using var automation = Factory.CreateClientForStranger();
        automation.DefaultRequestHeaders.Add("X-Test-Roles", AutomationRole);

        var response = await automation.PostAsync(
            "/members/bootstrap", content: null, TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.Forbidden);

        var me = await automation.GetAsync("/me", TestContext.Current.CancellationToken);
        var meBody = await me.Content.ReadFromJsonAsync<MeResponse>(TestContext.Current.CancellationToken);
        meBody!.Role.Should().BeNull("the refused bootstrap must not have created a membership");
    }

    [Fact]
    public async Task Token_WithAnUnrelatedRole_IsRefused()
    {
        using var client = Factory.CreateClientForStranger();
        client.DefaultRequestHeaders.Add("X-Test-Roles", "Some.Other.Role");

        var response = await client.GetAsync("/me", TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.Forbidden);
    }

    [Fact]
    public async Task Token_WithAnUnrelatedScope_IsRefused()
    {
        using var client = Factory.CreateClientForStranger();
        client.DefaultRequestHeaders.Add("X-Test-Scp", "user_impersonation");

        var response = await client.GetAsync("/me", TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.Forbidden);
    }

    private sealed record MeResponse(Guid UserId, string Email, string? Role);
}
