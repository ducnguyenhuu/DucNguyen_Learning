using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using ArchitectureTests.Support;
using AwesomeAssertions;
using Xunit;

namespace ArchitectureTests;

/// <summary>
/// A background job (an <c>IHostedService</c> implementor or a <c>BackgroundService</c>
/// subclass) is a singleton with no request scope to resolve tenant context from. ADR-013 names
/// this as the most likely place for a global-filter bypass to happen, and its own Consequences
/// section lists closing this as a known weakness deferred to this roadmap slice. This gate closes
/// the most direct route: a job whose constructor takes <c>IdentityDbContext</c> or a
/// persistence-port interface directly, bypassing whatever request-scoped tenant resolution would
/// otherwise apply.
/// </summary>
/// <remarks>
/// <para>
/// <b>What this gate does not close.</b> A job that obtains a repository through service
/// location (e.g. resolving an <c>IServiceScopeFactory</c> and pulling a repository out of a
/// created scope inside <c>ExecuteAsync</c>) never names the dependency in its constructor, so
/// this structural, source-scanning gate cannot see it. A separate runtime backstop exists
/// precisely for that route; this gate and that one are complementary, not redundant.
/// </para>
/// <para>
/// <b>Honest limits of the ADR-013 citation in the failure message below.</b> ADR-013 states
/// that background jobs are a likely leak vector and says a requirement that they "resolve
/// tenant context explicitly" should be added in this roadmap slice — but it does not itself
/// prescribe *how* a job should do that; it defers the mechanism as future work. The message
/// below cites ADR-013 for the "why" only, and is explicit that no concrete "what to do
/// instead" mechanism exists yet in this codebase, rather than citing the ADR as if it already
/// answers that question.
/// </para>
/// </remarks>
public sealed class BackgroundJobGates
{
    // Matches "class X : BackgroundService" or "class X : IHostedService" (and interfaces or
    // base lists that include either, e.g. "class X : SomeBase, IHostedService"). Deliberately a
    // simple, direct text match rather than a transitive-inheritance resolver: this codebase's
    // conventions (confirmed by SourceScanner/RawSqlGates) are text-scanning, and there is no
    // multi-level BackgroundService/IHostedService hierarchy in this codebase to resolve.
    private static readonly Regex JobClassPattern = new(
        pattern: @"\bclass\s+(?<name>[A-Za-z_][A-Za-z0-9_]*)\s*:\s*(?<bases>[A-Za-z0-9_,<>\.\s]+)",
        options: RegexOptions.Compiled);

    private const string BackgroundServiceBaseType = "BackgroundService";
    private const string HostedServiceInterface = "IHostedService";

    // Matches a constructor declaration for a given class name, capturing its parameter list, so
    // each parameter's declared type can be checked against IdentityDbContext and the known
    // persistence-port set. Text-based like the class-declaration scan above: this looks for
    // "public ClassName(...)" (constructors are conventionally public in this codebase).
    private static Regex ConstructorPattern(string className) => new(
        pattern: $@"\b{Regex.Escape(className)}\s*\((?<parameters>[^)]*)\)",
        options: RegexOptions.Compiled);

    // The lookahead at the end (rather than consuming the trailing comma) leaves that comma in
    // place so it can anchor the *next* parameter's leading (?:^|,): consuming it here would
    // otherwise mean only the first parameter of a multi-parameter constructor is ever matched.
    private static readonly Regex ParameterTypePattern = new(
        pattern: @"(?:^|,)\s*(?<type>[A-Za-z_][A-Za-z0-9_<>\.\[\],\s]*?)\s+[A-Za-z_][A-Za-z0-9_]*\s*(?=,|$)",
        options: RegexOptions.Compiled);

    [Fact]
    public void BackgroundJobs_DoNotTakeIdentityDbContextOrAPersistencePortDirectly()
    {
        var repoRoot = ProjectFile.GetRepoRoot();
        var sourceRoot = Path.Combine(repoRoot, "src");
        var knownPorts = PersistencePort.GetKnownPorts();

        var violations = FindBackgroundJobs(sourceRoot, repoRoot)
            .SelectMany(job => FindOffendingConstructorParameters(job, knownPorts)
                .Select(parameterType => $"{job.TypeName} ({job.FilePath}) takes {parameterType}"))
            .ToArray();

        violations.Should().BeEmpty(
            "a background job's constructor must not depend on IdentityDbContext or a " +
            "persistence port directly: it runs as a singleton with no request-scoped tenant " +
            "context to rely on, and ADR-013 names this as the most likely route for a " +
            "cross-tenant leak. ADR-013 explains why this matters but does not yet prescribe a " +
            "concrete mechanism for a job to resolve tenant context (that is deferred future " +
            "work) — today the fix is: don't take these dependencies directly in the " +
            "constructor at all. Resolve what the job needs per invocation instead — e.g. an " +
            "explicit tenant identifier passed into the job's execution method, or a " +
            "scope/repository created fresh inside ExecuteAsync for that one invocation, not " +
            "held as a singleton-scoped field. Offending job(s): " +
            string.Join(", ", violations));
    }

    [Fact]
    public void NoBackgroundJobTypeExistsUnderSrc()
    {
        // Mirrors CapabilityBoundaryGates.NoCapabilityOtherThanIdentityExistsUnderSrc: this pins
        // down that today's codebase has zero IHostedService/BackgroundService types at all, so
        // the gate above passes vacuously rather than because every job happens to be written
        // correctly. If this fails because a background job was legitimately added, that is
        // expected — update this pin and make sure the gate above actually exercises the new
        // type's constructor.
        var repoRoot = ProjectFile.GetRepoRoot();
        var sourceRoot = Path.Combine(repoRoot, "src");

        var jobs = FindBackgroundJobs(sourceRoot, repoRoot).ToArray();

        jobs.Should().BeEmpty(
            "this is a documented snapshot: no background job exists under src/ today. If this " +
            "fails because a background job was legitimately added, that is expected — update " +
            "this pin and confirm the constructor-parameter gate above covers it. Found: " +
            string.Join(", ", jobs.Select(j => $"{j.TypeName} ({j.FilePath})")));
    }

    private sealed record BackgroundJobType(string FilePath, string TypeName, string SourceText);

    private static IEnumerable<BackgroundJobType> FindBackgroundJobs(string sourceRoot, string repoRoot)
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
            var text = File.ReadAllText(filePath);
            var relativePath = Path.GetRelativePath(repoRoot, filePath).Replace('\\', '/');

            foreach (Match match in JobClassPattern.Matches(text))
            {
                var bases = match.Groups["bases"].Value;
                if (bases.Contains(BackgroundServiceBaseType, StringComparison.Ordinal)
                    || bases.Contains(HostedServiceInterface, StringComparison.Ordinal))
                {
                    yield return new BackgroundJobType(relativePath, match.Groups["name"].Value, text);
                }
            }
        }
    }

    private static IEnumerable<string> FindOffendingConstructorParameters(
        BackgroundJobType job,
        IReadOnlyCollection<string> knownPorts)
    {
        var constructorMatch = ConstructorPattern(job.TypeName).Match(job.SourceText);
        if (!constructorMatch.Success)
        {
            yield break;
        }

        var parameterList = constructorMatch.Groups["parameters"].Value;

        foreach (Match parameterMatch in ParameterTypePattern.Matches(parameterList))
        {
            var type = parameterMatch.Groups["type"].Value.Trim();
            var simpleTypeName = type.Split('.').Last();

            if (simpleTypeName == "IdentityDbContext" || knownPorts.Contains(simpleTypeName))
            {
                yield return type;
            }
        }
    }

    private static bool IsUnderExcludedDirectory(string path)
    {
        var segments = path.Split(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);

        return segments.Any(segment => segment is "bin" or "obj" or ".git");
    }
}
