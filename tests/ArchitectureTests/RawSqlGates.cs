using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using ArchitectureTests.Support;
using AwesomeAssertions;
using Xunit;

namespace ArchitectureTests;

/// <summary>
/// Confines raw-SQL execution under <c>src/</c> to a small, checked-in allow-list keyed by file
/// and enclosing member, so a raw-SQL call cannot be introduced or relocated without a reviewer
/// noticing it against this list.
/// </summary>
/// <remarks>
/// <para>
/// <b>Why an allow-list rather than an outright ban.</b> Raw SQL bypasses EF Core's tenant query
/// filter, so it is the most direct path to a cross-tenant data leak. Banning it outright isn't
/// possible today because one legitimate use exists — a row lock hint EF Core's LINQ surface has
/// no operator for (the single seeded entry in <see cref="AllowList"/> below). An allow-list
/// keyed by (file, member) lets that one call exist while failing loudly the moment raw SQL shows
/// up anywhere else, or the moment the audited call moves to a different member without the
/// allow-list moving with it.
/// </para>
/// <para>
/// <b>What "member" means as an allow-list key.</b> "Member" here means the enclosing method,
/// constructor, or property declaration that <see cref="SourceScanner"/>'s declaration-line regex
/// would find — i.e. its simple name, not a full signature. This does not distinguish between
/// overloads: two methods named <c>RemoveMembershipAsync</c> with different parameter lists in
/// the same file would collide in the allow-list, and an unaudited overload would pass under the
/// audited one's name. Nothing in this codebase overloads a method containing raw SQL today, so
/// this is accepted as a known, documented limitation rather than solved with a signature or
/// parameter-count key that would add complexity for a problem that does not yet exist. If
/// overloading of an allow-listed member's name ever happens, strengthen the key then.
/// </para>
/// <para>
/// <b>Text-matching limits and the escalation path.</b> Matches are found by scanning source
/// lines with a regex for known raw-SQL method names, not by parsing a syntax tree. That means a
/// call split across multiple lines, invoked through a local alias or a <c>using</c> alias, or
/// wrapped inside a helper/extension method that itself calls one of these APIs, can evade this
/// scan without tripping it. Loosening the regex further would not fix this: it would trade these
/// false negatives for false positives (e.g. matching a comment, a string literal, or an
/// unrelated method that merely shares a name), without addressing the underlying problem that
/// text matching has no notion of program structure. If this limitation ever matters in practice,
/// the fix is a Roslyn syntax-tree analyzer that resolves the actual invoked symbol, not a looser
/// regex.
/// </para>
/// </remarks>
public sealed class RawSqlGates
{
    private sealed record AllowListEntry(string FilePath, string MemberName, string Justification);

    // The allow-list itself. Every entry pairs a raw-SQL call site with the reason it exists, so
    // adding an entry cannot be a silent one-line diff — see JustificationsAreNonTrivial below.
    private static readonly AllowListEntry[] AllowList =
    {
        new(
            "src/Tenancy/Tenancy.Infrastructure/Persistence/MembershipRepository.cs",
            "RemoveMembershipAsync",
            "Takes an exclusive UPDLOCK/HOLDLOCK row lock on the tenant row before counting " +
            "active administrators, so a second concurrent removal targeting the same tenant " +
            "blocks until this transaction commits or rolls back. No EF Core LINQ operator " +
            "expresses a raw lock hint, so this is the one place raw SQL is the only tool " +
            "available for the guarantee this method makes."),
    };

    // Matches the raw-SQL entry points that bypass EF Core's tenant query filter: FromSqlRaw and
    // FromSqlInterpolated (queryable-returning), ExecuteSqlRaw/ExecuteSqlRawAsync and
    // ExecuteSqlInterpolated/ExecuteSqlInterpolatedAsync (command-executing), and Database.SqlQuery.
    // FromSqlRaw/FromSqlInterpolated have no Async-suffixed sibling in EF Core's actual API (they
    // return an IQueryable that is itself awaited via ToListAsync etc.), so only the Execute* forms
    // gain the Async variants below.
    private static readonly Regex RawSqlCallPattern = new(
        pattern: @"\b(FromSqlRaw|FromSqlInterpolated|ExecuteSqlRaw(?:Async)?|ExecuteSqlInterpolated(?:Async)?|SqlQuery(?:Async)?)\s*[<(]",
        options: RegexOptions.Compiled);

    // Reuses SourceScanner's own declaration-line pattern so "which member does this line belong
    // to" agrees with what SourceScanner.EnumerateMembers() would report for the same file.
    // SourceScanner only reports declaration lines, not a line-to-member mapping, so the same
    // regex is applied here as a rolling "current enclosing member" tracker while scanning a
    // file's lines top to bottom.
    private static readonly Regex DeclarationPattern = new(
        pattern:
            @"^\s*(?:\[[^\]]*\]\s*)*" +
            @"(?:public|private|protected|internal|static|sealed|abstract|virtual|override|readonly|async|partial|new|extern|unsafe|\s)+" +
            @"\b(?:class|interface|struct|record|enum|event)\b\s+(?<name>[A-Za-z_][A-Za-z0-9_]*)" +
            @"|^\s*(?:\[[^\]]*\]\s*)*" +
            @"(?:public|private|protected|internal|static|sealed|abstract|virtual|override|readonly|async|partial|new|extern|unsafe)\s+" +
            @"(?:[\w<>\[\],.?]+\s+)+(?<name>[A-Za-z_][A-Za-z0-9_]*)\s*(?:\(|\{|=>|;)",
        options: RegexOptions.Compiled);

    [Fact]
    public void RawSqlCalls_AreAllOnTheAllowList()
    {
        var repoRoot = ProjectFile.GetRepoRoot();
        var sourceRoot = Path.Combine(repoRoot, "src");

        var violations = FindRawSqlCalls(sourceRoot, repoRoot)
            .Where(call => !AllowList.Any(entry =>
                entry.FilePath == call.FilePath && entry.MemberName == call.MemberName))
            .ToArray();

        violations.Should().BeEmpty(
            "raw SQL bypasses EF Core's tenant query filter and must be confined to the " +
            "checked-in allow-list in RawSqlGates.cs — found unlisted call(s): " +
            string.Join(", ", violations.Select(v => $"{v.FilePath} / {v.MemberName}")));
    }

    [Fact]
    public void AllowListEntries_HaveANonTrivialJustification()
    {
        var trivialEntries = AllowList
            .Where(entry => entry.Justification.Trim().Split(
                    separator: ' ',
                    options: StringSplitOptions.RemoveEmptyEntries).Length < 8)
            .Select(entry => $"{entry.FilePath} / {entry.MemberName}")
            .ToArray();

        trivialEntries.Should().BeEmpty(
            "every allow-list entry must carry a real, reviewable justification (not a " +
            "placeholder like \"ok\") so adding an entry can't be a silent one-line diff — " +
            $"entries with a too-short justification: {string.Join(", ", trivialEntries)}");
    }

    private static IEnumerable<SourceMember> FindRawSqlCalls(string sourceRoot, string repoRoot)
    {
        if (!Directory.Exists(sourceRoot))
        {
            yield break;
        }

        var sourceFiles = Directory
            .EnumerateFiles(sourceRoot, "*.cs", SearchOption.AllDirectories)
            .Where(path => !IsUnderExcludedDirectory(path));

        foreach (var filePath in sourceFiles)
        {
            var relativePath = Path.GetRelativePath(repoRoot, filePath).Replace('\\', '/');
            string? currentMember = null;

            foreach (var line in File.ReadLines(filePath))
            {
                var declarationMatch = DeclarationPattern.Match(line);
                if (declarationMatch.Success)
                {
                    currentMember = declarationMatch.Groups["name"].Value;
                }

                if (RawSqlCallPattern.IsMatch(line))
                {
                    yield return new SourceMember(relativePath, currentMember ?? "<unknown>");
                }
            }
        }
    }

    private static bool IsUnderExcludedDirectory(string path)
    {
        var segments = path.Split(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);

        return segments.Any(segment => segment is "bin" or "obj" or ".git");
    }
}
