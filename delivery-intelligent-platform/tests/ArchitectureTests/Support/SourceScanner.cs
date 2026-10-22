using System.Text.RegularExpressions;

namespace ArchitectureTests.Support;

/// <summary>
/// A single top-level member declaration found in a source file, identified by the file it
/// lives in and the member's simple name. Allow-lists that gate risky APIs (raw SQL, reflection,
/// etc.) need both: the file alone doesn't distinguish an audited method from an unaudited one
/// declared right next to it in the same class.
/// </summary>
public sealed record SourceMember(string FilePath, string MemberName);

/// <summary>
/// Enumerates the .cs files under src/ and the members declared in each, so gates that need to
/// know "what code exists where" can ask this once instead of every gate re-walking the source
/// tree and re-parsing declarations itself.
/// </summary>
public static class SourceScanner
{
    // Matches a type or member declaration line: an access modifier followed eventually by an
    // identifier before a '(' (method), a '{' (type/property), or ';' (auto-property/field).
    // Deliberately text-based rather than a full Roslyn parse: gates only need "which member
    // name is this line inside", not a semantically complete syntax tree.
    public static readonly Regex DeclarationPattern = new(
        pattern:
            @"^\s*(?:\[[^\]]*\]\s*)*" +
            @"(?:public|private|protected|internal|static|sealed|abstract|virtual|override|readonly|async|partial|new|extern|unsafe|\s)+" +
            @"\b(?:class|interface|struct|record|enum|event)\b\s+(?<name>[A-Za-z_][A-Za-z0-9_]*)" +
            @"|^\s*(?:\[[^\]]*\]\s*)*" +
            @"(?:public|private|protected|internal|static|sealed|abstract|virtual|override|readonly|async|partial|new|extern|unsafe)\s+" +
            @"(?:[\w<>\[\],.?]+\s+)+(?<name>[A-Za-z_][A-Za-z0-9_]*)\s*(?:\(|\{|=>|;)",
        options: RegexOptions.Compiled);

    public static IReadOnlyList<SourceMember> EnumerateMembers()
    {
        var repoRoot = ProjectFile.GetRepoRoot();
        var sourceRoot = Path.Combine(repoRoot, "src");

        return EnumerateSourceFiles(sourceRoot)
            .SelectMany(filePath => EnumerateMembers(filePath, repoRoot))
            .ToArray();
    }

    private static IEnumerable<string> EnumerateSourceFiles(string sourceRoot)
    {
        if (!Directory.Exists(sourceRoot))
        {
            return [];
        }

        return Directory
            .EnumerateFiles(sourceRoot, "*.cs", SearchOption.AllDirectories)
            .Where(path => !IsUnderExcludedDirectory(path));
    }

    private static bool IsUnderExcludedDirectory(string path)
    {
        var segments = path.Split(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);

        return segments.Any(segment =>
            segment is "bin" or "obj" or ".git");
    }

    private static IEnumerable<SourceMember> EnumerateMembers(string filePath, string repoRoot)
    {
        var relativePath = Path.GetRelativePath(repoRoot, filePath).Replace('\\', '/');

        foreach (var line in File.ReadLines(filePath))
        {
            var match = DeclarationPattern.Match(line);
            if (match.Success)
            {
                yield return new SourceMember(relativePath, match.Groups["name"].Value);
            }
        }
    }
}
