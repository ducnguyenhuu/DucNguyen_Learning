using System.Text.RegularExpressions;

namespace ArchitectureTests.Support;

/// <summary>
/// Mechanically determines the set of "persistence port" interfaces — interfaces whose
/// implementing class lives under a directory path containing a <c>Persistence</c> segment
/// (e.g. <c>Identity.Infrastructure/Persistence/UserRepository.cs</c> implementing
/// <c>IUserRepository</c>).
/// </summary>
/// <remarks>
/// <para>
/// <b>Why namespace/path-based rather than a naming convention.</b> Guessing "any interface
/// named <c>I*Repository</c>" would be a naming-convention heuristic, not a mechanical rule
/// tied to where the implementation actually lives. This scans for
/// <c>class SomeType : ISomeInterface</c>-shaped declarations inside files whose directory
/// path contains a <c>Persistence</c> segment, and collects the interface names those classes
/// implement. That set is exactly "the interfaces a caller depends on when it wants direct
/// persistence access" — the thing FR-012 needs a background job's constructor to avoid.
/// </para>
/// <para>
/// <b>Why <c>ICallerContext</c>-style abstractions fall outside this set without a
/// special case.</b> The rule only counts an interface if a class implementing it lives under
/// a <c>Persistence</c> directory. Request-scoped abstractions like the caller context are
/// implemented under a <c>Security</c> directory in this codebase, not <c>Persistence</c>, so
/// they are excluded by the rule itself — no explicit exclusion list is needed. If that ever
/// stops being true (e.g. a caller-context implementation moves under a <c>Persistence</c>
/// path), this comment's assumption should be revisited rather than silently trusted.
/// </para>
/// <para>
/// <b>Text-matching limits.</b> Like <see cref="SourceScanner"/> and <c>RawSqlGates</c>, this
/// is a line-based regex scan, not a compiled-symbol lookup. A class implementing an interface
/// via a base-class chain (rather than declaring the interface directly on the class itself),
/// or an interface list split unusually across lines, could evade detection. This is accepted
/// for the same reason the sibling gates accept it: the codebase's actual declarations are
/// simple today, and a Roslyn-based analyzer is the documented escalation path if that changes.
/// </para>
/// </remarks>
public static class PersistencePort
{
    // Matches "class SomeType : ISomeInterface[, IOther, ...]" and captures each interface name
    // (an identifier starting with 'I' followed by an uppercase letter, the common .NET
    // interface-naming convention already used throughout this codebase).
    private static readonly Regex ClassWithInterfacesPattern = new(
        pattern: @"\bclass\s+[A-Za-z_][A-Za-z0-9_]*\s*:\s*(?<bases>[A-Za-z0-9_,<>\.\s]+)",
        options: RegexOptions.Compiled);

    private static readonly Regex InterfaceNamePattern = new(
        pattern: @"\bI[A-Z][A-Za-z0-9_]*\b",
        options: RegexOptions.Compiled);

    /// <summary>
    /// Returns the set of interface names implemented by any class declared under a directory
    /// whose path contains a <c>Persistence</c> segment, scanning source files under
    /// <c>src/</c>.
    /// </summary>
    public static IReadOnlyCollection<string> GetKnownPorts()
    {
        var repoRoot = ProjectFile.GetRepoRoot();
        var sourceRoot = Path.Combine(repoRoot, "src");

        if (!Directory.Exists(sourceRoot))
        {
            return Array.Empty<string>();
        }

        var ports = new HashSet<string>(StringComparer.Ordinal);

        var persistenceFiles = Directory
            .EnumerateFiles(sourceRoot, "*.cs", SearchOption.AllDirectories)
            .Where(path => !IsUnderExcludedDirectory(path))
            .Where(IsUnderPersistenceDirectory);

        foreach (var filePath in persistenceFiles)
        {
            foreach (var line in File.ReadLines(filePath))
            {
                var classMatch = ClassWithInterfacesPattern.Match(line);
                if (!classMatch.Success)
                {
                    continue;
                }

                foreach (Match interfaceMatch in InterfaceNamePattern.Matches(classMatch.Groups["bases"].Value))
                {
                    ports.Add(interfaceMatch.Value);
                }
            }
        }

        return ports;
    }

    private static bool IsUnderPersistenceDirectory(string filePath)
    {
        var segments = filePath.Split(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);

        return segments.Any(segment => segment == "Persistence");
    }

    private static bool IsUnderExcludedDirectory(string path)
    {
        var segments = path.Split(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);

        return segments.Any(segment => segment is "bin" or "obj" or ".git");
    }
}
