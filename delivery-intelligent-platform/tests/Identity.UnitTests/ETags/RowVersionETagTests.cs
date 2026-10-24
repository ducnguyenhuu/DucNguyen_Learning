using AwesomeAssertions;
using Identity.Api.ETags;
using Xunit;

namespace Identity.UnitTests.ETags;

/// <summary>
/// Unit tests for <see cref="RowVersionETag"/> (T057) — pure, dependency-free encode/decode
/// logic, so no fake repository or database ceremony is needed here.
/// </summary>
public class RowVersionETagTests
{
    [Fact]
    public void ToETag_ThenFromIfMatch_RoundTripsOriginalBytes()
    {
        byte[] rowVersion = [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x07, 0xD1];

        var etag = RowVersionETag.ToETag(rowVersion);
        var decoded = RowVersionETag.FromIfMatch(etag);

        decoded.Should().Equal(rowVersion);
    }

    [Fact]
    public void ToETag_WrapsBase64PayloadInDoubleQuotes()
    {
        byte[] rowVersion = [0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08];

        var etag = RowVersionETag.ToETag(rowVersion);

        etag.Should().Be($"\"{Convert.ToBase64String(rowVersion)}\"");
    }

    [Fact]
    public void ToETag_NullRowVersion_ThrowsArgumentNullException()
    {
        var act = () => RowVersionETag.ToETag(null!);

        act.Should().Throw<ArgumentNullException>();
    }

    [Fact]
    public void FromIfMatch_TolerantOfWeakEtagPrefix()
    {
        byte[] rowVersion = [0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF, 0x00, 0x11];
        var strongEtag = RowVersionETag.ToETag(rowVersion);
        var weakEtag = "W/" + strongEtag;

        var decoded = RowVersionETag.FromIfMatch(weakEtag);

        decoded.Should().Equal(rowVersion);
    }

    [Theory]
    [InlineData("")]
    [InlineData("   ")]
    [InlineData(null)]
    public void FromIfMatch_NullOrWhitespace_ThrowsArgumentException(string? value)
    {
        var act = () => RowVersionETag.FromIfMatch(value!);

        act.Should().Throw<ArgumentException>();
    }

    [Theory]
    [InlineData("not-quoted-base64")]
    [InlineData("\"unquoted")]
    [InlineData("unquoted\"")]
    [InlineData("\"")]
    public void FromIfMatch_MissingOrMismatchedQuotes_ThrowsFormatException(string malformed)
    {
        var act = () => RowVersionETag.FromIfMatch(malformed);

        act.Should().Throw<FormatException>();
    }

    [Fact]
    public void FromIfMatch_QuotedButInvalidBase64_ThrowsFormatException()
    {
        var act = () => RowVersionETag.FromIfMatch("\"not valid base64!!\"");

        act.Should().Throw<FormatException>();
    }
}
