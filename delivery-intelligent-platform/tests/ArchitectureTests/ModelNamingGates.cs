using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using ArchitectureTests.Support;
using AwesomeAssertions;
using Xunit;

namespace ArchitectureTests;

/// <summary>
/// Fails the build when a hardcoded AI-model identifier string shows up in production code
/// under <c>src/</c>, scanning for a small, explicit list of known model-name prefixes.
/// </summary>
/// <remarks>
/// <para>
/// <b>Why this matters even without a provider SDK.</b> No provider SDK is referenced in the
/// solution today (see <c>DependencyPinGates</c>), so nothing under <c>src/</c> can actually call
/// a model right now. A hardcoded model-identifier string is still worth catching ahead of that:
/// it is inert today, but pinning a model name directly into application code (rather than
/// configuration) is the kind of thing that is far easier to prevent from ever landing than to
/// clean up once a real call site exists and depends on it.
/// </para>
/// <para>
/// <b>Scope: <c>src/**/*.cs</c> only — deliberately, not the whole repository.</b> This
/// repository names models throughout its documentation, specs, and commit trailers; a
/// repo-wide scan would fail on its own prose the first time it ran. Docs, specs, and tests are
/// out of scope by design, not by oversight.
/// </para>
/// <para>
/// <b>Pattern set: a small, explicit list, not a general heuristic.</b> The six prefixes below
/// (<c>gpt-</c>, <c>claude-</c>, <c>gemini-</c>, <c>llama-</c>, <c>text-embedding-</c>,
/// <c>o1-</c>) are matched case-sensitively, exactly as given — this is intentionally narrow
/// rather than an attempt to recognize every possible model name a provider might ever ship.
/// </para>
/// <para>
/// <b>Why "inside a string literal" and not "anywhere on the line."</b> A pure substring-anywhere
/// check would false-positive on an ordinary code comment mentioning this very tool by name (e.g.
/// a comment attributing generated code, in the style this repository's own commit trailers
/// use) — "claude-" appears in "claude-code" without the line containing an actual model
/// identifier. To avoid that, the pattern below requires the prefix to appear immediately after a
/// <c>"</c> character on the same line, which is a reasonable proxy for "inside a quoted string
/// literal" without going as far as parsing a syntax tree.
/// </para>
/// <para>
/// <b>Text-matching limits, stated honestly.</b> Like every other text-scanning gate in this
/// project (see <c>RawSqlGates</c>, <c>BackgroundJobGates</c>), this is a line-based regex scan,
/// not a compiled-symbol or syntax-tree analysis. A model identifier split across a multi-line
/// string, built up through string interpolation or concatenation, or introduced via a raw
/// string literal whose opening quote sequence differs from a single <c>"</c>, can evade this
/// same-line check without tripping it. Loosening the "must follow a quote" requirement would
/// trade these false negatives for the comment false-positive this gate exists to avoid, so it is
/// accepted as a known, documented limitation rather than solved here. If this ever matters in
/// practice, the fix is a Roslyn-based analyzer that inspects actual string-literal tokens, not a
/// looser regex.
/// </para>
/// </remarks>
public sealed class ModelNamingGates
{
    // The six clarified model-identifier prefixes. Case-sensitive, exact casing — not a
    // case-insensitive or broader match.
    private static readonly string[] ModelIdentifierPrefixes =
    {
        "gpt-",
        "claude-",
        "gemini-",
        "llama-",
        "text-embedding-",
        "o1-",
    };

    // Matches one of the known prefixes only when it immediately follows a '"' character on the
    // same line — a same-line proxy for "inside a quoted string literal," chosen to avoid
    // false-positiving on a code comment that merely mentions one of these names (e.g. this
    // tool's own name, "claude-code", inside an attribution comment).
    private static readonly Regex ModelIdentifierInStringLiteralPattern = new(
        pattern: "\"(?:" + string.Join("|", ModelIdentifierPrefixes.Select(Regex.Escape)) + ")",
        options: RegexOptions.Compiled);

    [Fact]
    public void SourceCode_ContainsNoHardcodedModelIdentifierStrings()
    {
        var repoRoot = ProjectFile.GetRepoRoot();
        var sourceRoot = Path.Combine(repoRoot, "src");

        var violations = FindModelIdentifierStrings(sourceRoot, repoRoot).ToArray();

        violations.Should().BeEmpty(
            "a hardcoded AI-model identifier string must not appear in production code under " +
            "src/ — found in: " + string.Join(", ", violations));
    }

    private static IEnumerable<string> FindModelIdentifierStrings(string sourceRoot, string repoRoot)
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
            var lineNumber = 0;

            foreach (var line in File.ReadLines(filePath))
            {
                lineNumber++;

                if (ModelIdentifierInStringLiteralPattern.IsMatch(line))
                {
                    yield return $"{relativePath}:{lineNumber}";
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
