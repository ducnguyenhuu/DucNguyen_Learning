using AwesomeAssertions;
using Identity.Domain.Abstractions;
using Identity.Infrastructure.Security;
using Xunit;

namespace Identity.UnitTests.Authorization;

/// <summary>
/// Pins <see cref="HttpContextCallerContext"/>'s fail-closed contract (ADR-025). The default
/// <see cref="Role"/> is <see cref="Role.Administrator"/>, so an unresolved context that returned
/// defaults instead of throwing would silently grant administrator powers to whatever code read
/// it too early.
/// </summary>
public class HttpContextCallerContextTests
{
    [Fact]
    public void UserId_BeforeResolve_Throws()
    {
        var callerContext = new HttpContextCallerContext();

        Action act = () => _ = callerContext.UserId;

        act.Should().Throw<InvalidOperationException>();
    }

    [Fact]
    public void Role_BeforeResolve_Throws()
    {
        var callerContext = new HttpContextCallerContext();

        Action act = () => _ = callerContext.Role;

        act.Should().Throw<InvalidOperationException>();
    }

    [Fact]
    public void Resolve_ThenRead_ReturnsResolvedValues()
    {
        var callerContext = new HttpContextCallerContext();
        var userId = UserId.New();

        callerContext.Resolve(userId, Role.Reader);

        callerContext.UserId.Should().Be(userId);
        callerContext.Role.Should().Be(Role.Reader);
    }

    /// <summary>
    /// Resolution is a one-time event per request scope; a second call indicates a bug in the
    /// resolution filter and must not silently replace the first caller.
    /// </summary>
    [Fact]
    public void Resolve_CalledTwice_Throws_AndKeepsFirstResolution()
    {
        var callerContext = new HttpContextCallerContext();
        var firstUserId = UserId.New();
        callerContext.Resolve(firstUserId, Role.Member);

        Action act = () => callerContext.Resolve(UserId.New(), Role.Administrator);

        act.Should().Throw<InvalidOperationException>();
        callerContext.UserId.Should().Be(firstUserId);
        callerContext.Role.Should().Be(Role.Member);
    }
}
