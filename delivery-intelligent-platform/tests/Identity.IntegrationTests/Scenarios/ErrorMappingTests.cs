using ArchitectureTests.Support;
using AwesomeAssertions;
using Identity.IntegrationTests.Infrastructure;
using Xunit;

namespace Identity.IntegrationTests.Scenarios;

/// <summary>
/// End-to-end verification that the global <c>ProblemDetailsHandler</c> maps <c>DomainException</c>
/// to a 400 response rather than falling back to a blanket 500. Hits
/// <see cref="TestOnlyThrowingEndpoints"/>'s routes (see that type's remarks for why no real
/// production route can be used for this: every real endpoint already catches
/// <c>DomainException</c>/<c>ConflictException</c> locally before it can reach the global
/// handler) so the assertion below still exercises the real HTTP pipeline, including the real
/// <c>UseExceptionHandler()</c> registration, rather than calling the handler directly.
/// </summary>
public sealed class ErrorMappingTests : IdentityIntegrationTestBase
{
    public ErrorMappingTests(SqlServerFixture sqlServerFixture, ApiFactory factory)
        : base(sqlServerFixture, factory)
    {
    }

    [CoversRequirement("FR-019")]
    [Fact]
    public async Task Get_RouteThatThrowsUnhandledDomainException_ReturnsBadRequest()
    {
        using var client = Factory.CreateClient();

        var response = await client.GetAsync(
            TestOnlyThrowingEndpoints.DomainExceptionPath,
            TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(System.Net.HttpStatusCode.BadRequest);
    }
}
