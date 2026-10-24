using AwesomeAssertions;
using Identity.Application.Invitations;
using Xunit;

namespace Identity.UnitTests.Invitations;

/// <summary>
/// Unit tests for <see cref="InvitationToken"/> (T070) — pure, dependency-free crypto helper
/// logic, so no fake repository or database ceremony is needed here.
/// </summary>
public class InvitationTokenTests
{
    [Fact]
    public void Generate_ProducesNonEmptyToken()
    {
        var token = InvitationToken.Generate();

        token.Should().NotBeNullOrWhiteSpace();
    }

    [Fact]
    public void Generate_ProducesDistinctTokensAcrossCalls()
    {
        var first = InvitationToken.Generate();
        var second = InvitationToken.Generate();

        first.Should().NotBe(second);
    }

    [Fact]
    public void Hash_IsDeterministic_SameTokenHashesTheSameWayTwice()
    {
        var token = InvitationToken.Generate();

        var first = InvitationToken.Hash(token);
        var second = InvitationToken.Hash(token);

        first.Should().Equal(second);
    }

    [Fact]
    public void Verify_SucceedsForMatchingToken()
    {
        var token = InvitationToken.Generate();
        var hash = InvitationToken.Hash(token);

        InvitationToken.Verify(token, hash).Should().BeTrue();
    }

    [Fact]
    public void Verify_FailsForNonMatchingToken()
    {
        var token = InvitationToken.Generate();
        var otherToken = InvitationToken.Generate();
        var hash = InvitationToken.Hash(token);

        InvitationToken.Verify(otherToken, hash).Should().BeFalse();
    }

    [Fact]
    public void Hash_OutputIsExactly32Bytes()
    {
        var token = InvitationToken.Generate();

        var hash = InvitationToken.Hash(token);

        hash.Should().HaveCount(32);
    }
}
