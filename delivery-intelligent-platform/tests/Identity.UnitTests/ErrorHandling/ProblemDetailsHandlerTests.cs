using AwesomeAssertions;
using Microsoft.AspNetCore.Http;
using Microsoft.Extensions.Logging.Abstractions;
using Identity.Api.ErrorHandling;
using Identity.Domain.Abstractions;
using Xunit;

namespace Identity.UnitTests.ErrorHandling;

/// <summary>
/// Verifies <see cref="ProblemDetailsHandler"/>'s exception-to-status-code mapping:
/// <see cref="DomainException"/> maps to 400, <see cref="ConflictException"/> maps to 409, and
/// any other, unrecognized exception falls back to a blanket 500.
/// </summary>
public class ProblemDetailsHandlerTests
{
    private static ProblemDetailsHandler CreateHandler() =>
        new(NullLogger<ProblemDetailsHandler>.Instance);

    private static DefaultHttpContext CreateHttpContext()
    {
        var httpContext = new DefaultHttpContext();
        httpContext.Response.Body = new MemoryStream();
        return httpContext;
    }

    [Fact]
    public async Task TryHandleAsync_GivenDomainException_SetsStatusCode400()
    {
        var handler = CreateHandler();
        var httpContext = CreateHttpContext();

        var handled = await handler.TryHandleAsync(
            httpContext, new DomainException("invariant violated"), CancellationToken.None);

        handled.Should().BeTrue();
        httpContext.Response.StatusCode.Should().Be(StatusCodes.Status400BadRequest);
    }

    [Fact]
    public async Task TryHandleAsync_GivenConflictException_SetsStatusCode409()
    {
        var handler = CreateHandler();
        var httpContext = CreateHttpContext();

        var handled = await handler.TryHandleAsync(
            httpContext, new ConflictException("already exists"), CancellationToken.None);

        handled.Should().BeTrue();
        httpContext.Response.StatusCode.Should().Be(StatusCodes.Status409Conflict);
    }

    [Fact]
    public async Task TryHandleAsync_GivenUnrelatedException_SetsStatusCode500()
    {
        var handler = CreateHandler();
        var httpContext = CreateHttpContext();

        var handled = await handler.TryHandleAsync(
            httpContext, new InvalidOperationException("something else"), CancellationToken.None);

        handled.Should().BeTrue();
        httpContext.Response.StatusCode.Should().Be(StatusCodes.Status500InternalServerError);
    }
}
