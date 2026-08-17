using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using ArchitectureTests.Support;
using AwesomeAssertions;
using Xunit;

namespace ArchitectureTests;

/// <summary>
/// <c>IgnoreQueryFilters()</c> called with no arguments disables every global
/// query filter EF Core knows about, including the tenant-scoping <c>"TenantFilter"</c> and any
/// other filter added later. The named form — <c>IgnoreQueryFilters(["TenantFilter"])</c> or the
/// equivalent <c>IgnoreQueryFilters(new[] { "TenantFilter" })</c> — disables only the one filter
/// the caller actually means to bypass. This gate fails on the bare form and permits the named
/// form, so a reviewer never has to re-derive by hand whether a given call site is narrowly
/// scoped or a blanket bypass.
/// </summary>
/// <remarks>
/// <para>
/// <b>Today's compliant baseline.</b> Four call sites use <c>IgnoreQueryFilters</c> today, all in
/// the named form:
/// </para>
/// <list type="bullet">
/// <item><description>
/// <c>src/Tenancy/Tenancy.Infrastructure/Persistence/InvitationRepository.cs:67</c>, inside
/// <c>FindByTokenHashAsync</c> — looks up an invitation by its bare token hash before any tenant
/// is known.
/// </description></item>
/// <item><description>
/// <c>src/Tenancy/Tenancy.Infrastructure/Persistence/MembershipRepository.cs:82</c>, inside
/// <c>RemoveMembershipAsync</c> — discovers a membership's owning tenant by id alone.
/// </description></item>
/// <item><description>
/// <c>src/Tenancy/Tenancy.Infrastructure/Persistence/MembershipRepository.cs:105</c>, also inside
/// <c>RemoveMembershipAsync</c> — a second, later call in the same method, after the tenant has
/// been discovered and set explicitly.
/// </description></item>
/// <item><description>
/// <c>src/Tenancy/Tenancy.Infrastructure/Persistence/Audited/MembershipDirectory.cs:40</c>, inside
/// <c>GetMembershipsForUserCoreAsync</c> — the sanctioned cross-tenant listing used by
/// <c>GET /tenants</c>, paired with a mandatory <c>UserId</c> predicate in the same query.
/// </description></item>
/// </list>
/// <para>
/// <b>Text-matching limits.</b> Matches are found by scanning source lines with a regex, not by
/// parsing a syntax tree, following the same convention as <c>RawSqlGates</c> and
/// <c>BackgroundJobGates</c>. A call split across multiple lines, or reached through a helper or
/// extension method that itself calls <c>IgnoreQueryFilters()</c> bare, can evade this scan. If
/// that limitation ever matters in practice, the fix is a Roslyn syntax-tree analyzer that
/// resolves the actual invocation, not a looser regex.
/// </para>
/// </remarks>
public sealed class TenantIsolationGates
{
    // Matches only the bare, no-argument form: empty parentheses, allowing whitespace between
    // them. Any non-empty argument — an old-style array literal, a collection expression, a
    // variable — puts content between the parens and does not match, which is exactly the named
    // form this gate must permit.
    private static readonly Regex BareIgnoreQueryFiltersPattern = new(
        pattern: @"\bIgnoreQueryFilters\s*\(\s*\)",
        options: RegexOptions.Compiled);

    // Reuses SourceScanner's own declaration-line pattern so "which member does this line belong
    // to" agrees with what SourceScanner.EnumerateMembers() would report for the same file, the
    // same rolling "current enclosing member" tracker used by RawSqlGates and BackgroundJobGates.
    private static readonly Regex DeclarationPattern = SourceScanner.DeclarationPattern;

    [Fact]
    public void IgnoreQueryFiltersCalls_NeverUseTheBareForm()
    {
        var repoRoot = ProjectFile.GetRepoRoot();
        var sourceRoot = Path.Combine(repoRoot, "src");

        var violations = FindBareIgnoreQueryFiltersCalls(sourceRoot, repoRoot).ToArray();

        violations.Should().BeEmpty(
            "the bare IgnoreQueryFilters() disables every global query filter, including the " +
            "tenant-scoping \"TenantFilter\" and any other filter added later — use the named " +
            "form IgnoreQueryFilters([\"TenantFilter\"]) (or IgnoreQueryFilters(new[] { " +
            "\"TenantFilter\" })) to disable only the one filter the call site actually needs to " +
            "bypass. Offending call(s): " +
            string.Join(", ", violations.Select(v => $"{v.FilePath} / {v.MemberName}")));
    }

    private static IEnumerable<SourceMember> FindBareIgnoreQueryFiltersCalls(
        string sourceRoot,
        string repoRoot)
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

                // Skip comment lines (including doc comments): several call sites are documented
                // with prose that mentions "IgnoreQueryFilters()" in passing to explain what the
                // named form deliberately avoids doing — that prose is not a call site.
                if (line.TrimStart().StartsWith("//", StringComparison.Ordinal))
                {
                    continue;
                }

                if (BareIgnoreQueryFiltersPattern.IsMatch(line))
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
