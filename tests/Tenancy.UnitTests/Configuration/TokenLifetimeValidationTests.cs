using ArchitectureTests.Support;
using AwesomeAssertions;
using Tenancy.Api.Configuration;
using Xunit;

namespace Tenancy.UnitTests.Configuration;

/// <summary>
/// Proves the T077 startup-time check for FR-016/Assumption 7's revocation-staleness
/// trade-off actually fires: an <c>ExpectedMaxLifetimeMinutes</c> above the one-hour bound
/// must throw at boot, and any value at or under that bound must not.
/// </summary>
public sealed class TokenLifetimeValidationTests
{
    [CoversRequirement("FR-016")]
    [Theory]
    [InlineData(1)]
    [InlineData(59)]
    [InlineData(60)]
    public void AssertWithinRevocationWindow_AtOrUnderOneHour_DoesNotThrow(int minutes)
    {
        var act = () => TokenLifetimeValidation.AssertWithinRevocationWindow(minutes);

        act.Should().NotThrow();
    }

    [CoversRequirement("FR-016")]
    [Theory]
    [InlineData(61)]
    [InlineData(120)]
    public void AssertWithinRevocationWindow_OverOneHour_Throws(int minutes)
    {
        var act = () => TokenLifetimeValidation.AssertWithinRevocationWindow(minutes);

        act.Should().Throw<InvalidOperationException>()
            .WithMessage("*FR-016*");
    }
}
