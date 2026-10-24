using System.Net;
using System.Net.Http.Json;
using ArchitectureTests.Support;
using Identity.IntegrationTests.Infrastructure;
using AwesomeAssertions;
using Xunit;

namespace Identity.IntegrationTests.Scenarios;

/// <summary>
/// <b>401 Unauthorized</b> for every non-health route when no <c>Authorization</c> header is
/// present at all (<see cref="TestAuthHandler"/>'s <c>NoResult()</c> path — not "present but
/// invalid", which <see cref="TokenValidationTests"/> covers). FR-002: an unauthenticated request
/// is rejected without disclosing any data.
/// </summary>
/// <remarks>
/// The theory includes the routes that are deliberately <em>not</em> member-only
/// (<c>GET /me</c>, <c>POST /members/bootstrap</c>, <c>POST /invitations/{token}/accept</c>):
/// being callable by a non-member never means being callable anonymously.
/// </remarks>
public sealed class UnauthenticatedTests : IdentityIntegrationTestBase
{
    public UnauthenticatedTests(SqlServerFixture sqlServerFixture, ApiFactory factory)
        : base(sqlServerFixture, factory)
    {
    }

    public static TheoryData<string, string> Routes() => new()
    {
        { "GET", "/me" },
        { "POST", "/members/bootstrap" },
        { "GET", "/members" },
        { "PATCH", "/members/0198a3c4-0000-7000-8000-000000000001" },
        { "DELETE", "/members/0198a3c4-0000-7000-8000-000000000001" },
        { "POST", "/invitations" },
        { "GET", "/invitations" },
        { "DELETE", "/invitations/0198a3c4-0000-7000-8000-000000000002" },
        { "POST", "/invitations/some-token/accept" },
    };

    [CoversRequirement("FR-002")]
    [Theory]
    [MemberData(nameof(Routes))]
    public async Task Route_WithNoAuthorizationHeader_ReturnsUnauthorized_AndDisclosesNothing(string method, string path)
    {
        using var client = Factory.CreateClient();
        using var request = new HttpRequestMessage(new HttpMethod(method), path);
        if (method is "POST" or "PATCH")
        {
            request.Content = JsonContent.Create(new { email = "someone@example.com", role = "Member" });
        }

        var response = await client.SendAsync(request, TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.Unauthorized);

        var body = await response.Content.ReadAsStringAsync(TestContext.Current.CancellationToken);
        body.Should().NotContain("someone@example.com");
    }
}
