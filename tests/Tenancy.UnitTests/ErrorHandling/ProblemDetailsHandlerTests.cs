using AwesomeAssertions;
using Microsoft.AspNetCore.Http;
using Microsoft.Extensions.Logging.Abstractions;
using Tenancy.Api.ErrorHandling;
using Tenancy.Domain.Abstractions;
using Xunit;

namespace Tenancy.UnitTests.ErrorHandling;

/// <summary>
/// Proof that today's <see cref="ProblemDetailsHandler"/> maps every unhandled exception to a
/// blanket 500 — including <see cref="DomainException"/> and <see cref="ConflictException"/>,
/// which should instead map to 400 and 409 respectively. The two cases below are expected to FAIL
/// against the current, unmodified handler; only the plain-<see cref="Exception"/> case should
/// pass today, since staying at 500 for genuinely unrecognized exceptions is the handler's
/// intended behavior even after that mapping is added.
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
