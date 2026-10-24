using ArchitectureTests.Support;
using AwesomeAssertions;
using Identity.Domain.Abstractions;
using Identity.IntegrationTests.Infrastructure;
using Xunit;

namespace Identity.IntegrationTests.Scenarios;

/// <summary>
/// Error non-disclosure tests — black-box verification of the global <c>ProblemDetailsHandler</c>
/// (RFC 9457, zero exception detail) and the endpoints' own error responses across a variety of
/// error-triggering requests (FR-022).
/// </summary>
/// <remarks>
/// Each test provokes a different class of error (malformed route parameter, malformed request
/// body, a non-member probing the organization) and asserts the response body — whatever its
/// status code turns out to be — never contains a stack trace, exception type name,
/// connection-string fragment, raw SQL statement, or another member's identifying information.
/// </remarks>
public sealed class ErrorDisclosureTests : IdentityIntegrationTestBase
{

    public ErrorDisclosureTests(SqlServerFixture sqlServerFixture, ApiFactory factory)
        : base(sqlServerFixture, factory)
    {
    }

    [CoversRequirement("FR-022")]
    [Fact]
    public async Task Delete_Member_WithMalformedRouteId_DoesNotDiscloseSensitiveDetail()
    {
        var administrator = await Factory.SeedMemberAsync(Role.Administrator);

        using var client = Factory.CreateClientFor(administrator);

        // "not-a-guid" is a genuinely malformed user id — not a syntactically valid GUID at
        // all — so this exercises route-model-binding failure, whatever status it produces.
        var response = await client.DeleteAsync(
            "/members/not-a-guid",
            TestContext.Current.CancellationToken);

        var body = await response.Content.ReadAsStringAsync(TestContext.Current.CancellationToken);

        AssertNoSensitiveDisclosure(body);
    }

    [CoversRequirement("FR-022")]
    [Fact]
    public async Task Post_Invitations_WithMalformedJsonBody_DoesNotDiscloseSensitiveDetail()
    {
        var administrator = await Factory.SeedMemberAsync(Role.Administrator);

        using var client = Factory.CreateClientFor(administrator);
        client.DefaultRequestHeaders.Add("Idempotency-Key", Guid.NewGuid().ToString());

        using var malformedContent = new StringContent(
            "{ this is not valid json ",
            System.Text.Encoding.UTF8,
            "application/json");

        var response = await client.PostAsync(
            "/invitations",
            malformedContent,
            TestContext.Current.CancellationToken);

        var body = await response.Content.ReadAsStringAsync(TestContext.Current.CancellationToken);

        AssertNoSensitiveDisclosure(body);
    }

    /// <summary>
    /// A non-member probing the member list is refused, and the refusal body leaks nothing about
    /// who the members are.
    /// </summary>
    [CoversRequirement("FR-022")]
    [Fact]
    public async Task Get_Members_AsNonMember_DoesNotDiscloseMemberIdentity()
    {
        var administrator = await Factory.SeedMemberAsync(Role.Administrator, "secret-admin@example.com");

        using var client = Factory.CreateClientForStranger();

        var response = await client.GetAsync("/members", TestContext.Current.CancellationToken);

        var body = await response.Content.ReadAsStringAsync(TestContext.Current.CancellationToken);

        AssertNoSensitiveDisclosure(body);
        body.Should().NotContain(administrator.UserId.Value.ToString());
        body.Should().NotContain(administrator.Email);
    }

    /// <summary>
    /// Shared assertion helper (per task brief): a response body must never contain a stack
    /// trace, exception type name, connection-string fragment, or raw SQL statement fragment.
    /// Member-identifier disclosure is checked per-test (the sensitive value differs by
    /// scenario), not here.
    /// </summary>
    private static void AssertNoSensitiveDisclosure(string body)
    {
        body.Should().NotContain("Exception");
        body.Should().NotContain("StackTrace");
        body.Should().NotContain("   at ");
        body.Should().NotContain("System.");

        body.Should().NotContain("Server=");
        body.Should().NotContain("Password=");
        body.Should().NotContain("User Id=");

        body.Should().NotContainEquivalentOf("SELECT ");
        body.Should().NotContainEquivalentOf("INSERT ");
        body.Should().NotContainEquivalentOf("UPDATE ");
        body.Should().NotContainEquivalentOf("FROM [");
        body.Should().NotContainEquivalentOf("WHERE [");
    }
}
