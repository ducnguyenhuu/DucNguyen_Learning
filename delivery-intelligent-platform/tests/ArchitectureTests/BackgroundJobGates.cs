using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using ArchitectureTests.Support;
using AwesomeAssertions;
using Xunit;

namespace ArchitectureTests;

/// <summary>
/// A background job (an <c>IHostedService</c> implementor or a <c>BackgroundService</c>
/// subclass) is registered as a singleton and lives for the whole process. <c>IdentityDbContext</c>
/// and every persistence port are registered <b>scoped</b>. A singleton that takes one of them in
/// its constructor captures a single instance for its entire lifetime — a captive dependency.
/// That one <c>DbContext</c> is then shared across every execution of the job: its change tracker
/// keeps growing and keeps serving stale entities from earlier runs, a failed <c>SaveChanges</c>
/// leaves it poisoned for every later run, and, because <c>DbContext</c> is not thread-safe, any
/// overlap between executions (or with a request that somehow shares it) corrupts its state. This
/// gate closes the most direct route to that bug: a job whose constructor names
/// <c>IdentityDbContext</c> or a persistence-port interface.
/// </summary>
/// <remarks>
/// <para>
/// <b>What to do instead.</b> Take an <c>IServiceScopeFactory</c> in the constructor and create a
/// fresh scope inside each execution, resolving the <c>DbContext</c> or repository from that
/// scope and disposing it when the execution ends. That is the standard .NET pattern for scoped
/// work inside a hosted service, and it is not what this gate forbids.
/// </para>
/// <para>
/// <b>What this gate does not close.</b> It reads constructors only. A job that creates a scope
/// correctly but then stores the resolved repository in a field and reuses it across executions
/// rebuilds the same captive dependency by hand, and this structural, source-scanning gate cannot
/// see that. ASP.NET Core's scope validation (on by default in the Development environment) also
/// rejects a scoped service injected into a singleton constructor at startup, but only in
/// Development and only when the service is resolved; this gate fails in CI regardless of
/// environment.
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
            "persistence port directly: the job is a singleton and those are scoped, so it " +
            "would capture one DbContext for the life of the process — shared across every " +
            "execution, accumulating stale tracked entities, and not thread-safe. Take an " +
            "IServiceScopeFactory instead and create a fresh scope (and resolve the DbContext " +
            "or repository from it) inside each execution, not held as a field. " +
            "Offending job(s): " +
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
