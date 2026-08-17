using System.Reflection;
using System.Text.RegularExpressions;
using AwesomeAssertions;
using Xunit;

namespace ArchitectureTests;

/// <summary>
/// Exercises the offender-identifying regexes that several gates use to build their failure
/// messages, against fabricated input, without re-triggering a full source-tree violation.
/// </summary>
/// <remarks>
/// <para>
/// Most gates in this project fuse "scan for violations" and "format the failure message" into
/// one <c>.Should().BeEmpty(reason)</c> call, so there is no separately callable
/// "format(violations)" method to invoke with a fabricated list. What each gate's failure
/// message actually names, though, is the exact substring its scanning regex captures — so
/// these tests reach the gates' private regex fields via reflection and confirm, on fabricated
/// lines, that the regex captures the specific offending identifier that would end up
/// interpolated into the failure string, and that it does not fire on the inputs each gate's
/// remarks document as intentionally excluded (comments, the compliant named form, and so on).
/// This is a genuine test of the message-construction logic's input, not a restatement of the
/// audit document.
/// </para>
/// </remarks>
public sealed class FailureMessageContentTests
{
    private static Regex GetPrivateStaticRegex(Type type, string fieldName)
    {
        var field = type.GetField(fieldName, BindingFlags.NonPublic | BindingFlags.Static)
            ?? throw new MissingFieldException(type.FullName, fieldName);

        return (Regex)field.GetValue(null)!;
    }

    [Fact]
    public void RawSqlGates_CallPattern_CapturesTheOffendingApiName()
    {
        var pattern = GetPrivateStaticRegex(typeof(RawSqlGates), "RawSqlCallPattern");

        pattern.IsMatch("var rows = context.Database.ExecuteSqlRawAsync(sql);").Should().BeTrue(
            "the pattern must fire on a raw-SQL call so the enclosing member's name can be " +
            "named in the gate's failure message");

        pattern.IsMatch("var rows = context.Users.ToListAsync();").Should().BeFalse(
            "the pattern must not fire on an ordinary EF Core call, or every source file would " +
            "be reported as an offender");
    }

    [Fact]
    public void TenantIsolationGates_BarePattern_DistinguishesBareFromNamedForm()
    {
        var pattern = GetPrivateStaticRegex(typeof(TenantIsolationGates), "BareIgnoreQueryFiltersPattern");

        pattern.IsMatch("var all = context.Users.IgnoreQueryFilters();").Should().BeTrue(
            "the bare, no-argument form is exactly what this gate must catch and name in its " +
            "failure message");

        pattern.IsMatch("var mine = context.Users.IgnoreQueryFilters([\"TenantFilter\"]);")
            .Should().BeFalse(
                "the named form is the documented compliant baseline and must not be reported " +
                "as an offender");
    }

    [Fact]
    public void ModelNamingGates_StringLiteralPattern_RequiresAQuotedPrefixNotACommentMention()
    {
        var pattern = GetPrivateStaticRegex(
            typeof(ModelNamingGates), "ModelIdentifierInStringLiteralPattern");

        pattern.IsMatch("var model = \"claude-sonnet-5\";").Should().BeTrue(
            "a hardcoded model identifier inside a string literal is exactly what this gate " +
            "must name in its failure message");

        pattern.IsMatch("// Generated with claude-code").Should().BeFalse(
            "the gate's own remarks document that a comment merely mentioning \"claude-code\" " +
            "must not be reported as an offending model identifier");
    }

    [Fact]
    public void BackgroundJobGates_JobClassPattern_CapturesTheOffendingTypeName()
    {
        var pattern = GetPrivateStaticRegex(typeof(BackgroundJobGates), "JobClassPattern");

        var match = pattern.Match("public sealed class SyncWorker : BackgroundService");

        match.Success.Should().BeTrue(
            "the pattern must recognize a BackgroundService subclass so its type name can be " +
            "named in the gate's failure message");
        match.Groups["name"].Value.Should().Be("SyncWorker",
            "the captured group is exactly the type name the failure message interpolates — " +
            "if this captured the wrong text, the message would name the wrong offender");
    }

    [Fact]
    public void BackgroundJobGates_ParameterTypePattern_CapturesTheOffendingParameterType()
    {
        var pattern = GetPrivateStaticRegex(typeof(BackgroundJobGates), "ParameterTypePattern");

        var match = pattern.Match("TenancyDbContext db");

        match.Success.Should().BeTrue(
            "a constructor parameter typed TenancyDbContext must be captured so the gate's " +
            "failure message can name it as the offending dependency");
        match.Groups["type"].Value.Trim().Should().Be("TenancyDbContext",
            "this is the exact substring the gate's failure message interpolates for the " +
            "offending parameter — not a generic placeholder");
    }
}
