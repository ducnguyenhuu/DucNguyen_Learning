using AwesomeAssertions;
using Xunit;

namespace Identity.UnitTests;

public class PlaceholderTests
{
    [Fact]
    public void Placeholder() => true.Should().BeTrue();
}
