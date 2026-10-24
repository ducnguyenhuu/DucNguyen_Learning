using AwesomeAssertions;
using Xunit;

namespace Identity.IntegrationTests;

public class PlaceholderTests
{
    [Fact]
    public void Placeholder() => true.Should().BeTrue();
}
