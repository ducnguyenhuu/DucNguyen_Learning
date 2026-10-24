using System.Reflection;
using System.Text.RegularExpressions;
using ArchitectureTests.Support;
using AwesomeAssertions;
using Xunit;

namespace ArchitectureTests;

/// <summary>
/// Verifies that spec 001's declared requirement-coverage claims — the
/// <see cref="CoversRequirementAttribute"/> usages scattered across
/// <c>Identity.UnitTests</c> and <c>Identity.IntegrationTests</c> — stay true over time: every one
/// of spec 001's twenty-six functional requirements still has at least one declaring test, and no
/// declaration names a requirement identifier that does not actually exist in spec 001.
/// </summary>
/// <remarks>
/// <para>
/// <b>What this gate detects.</b> Loss of a previously-made coverage claim. If someone deletes
/// the last test carrying <c>[CoversRequirement("FR-005")]</c>, or deletes the attribute usage
/// from a test while leaving the test itself in place, this gate turns red and names the
/// requirement that lost its coverage.
/// </para>
/// <para>
/// <b>What this gate does NOT detect.</b> Whether a test carrying <c>[CoversRequirement]</c>
/// actually, meaningfully exercises the requirement it names. A test that declares
/// <c>[CoversRequirement("FR-005")]</c> and then asserts something unrelated — or asserts nothing
/// at all — satisfies this gate while being worthless as real coverage. Whether each declaration
/// is substantively true was judged once, by hand, in a prior hand audit that produced the
/// project's coverage record; this gate exists to protect that hand audit from rotting as the
/// codebase changes, not to repeat or re-verify the judgement it made. A gate that could tell a
/// meaningful test from a decorative one would need to understand what each test's assertions
/// actually prove, which is a job for a human reader, not a reflection scan.
/// </para>
/// <para>
/// <b>Scope: spec 001 only, not this slice's own requirements.</b> This slice (spec 002,
/// architecture-tests) has its own functional requirements, including the ones that specify this
/// very gate. This gate is scoped to spec 001's twenty-six requirements only, as literally
/// specified — it does not also require a declared coverage claim for spec 002's own
/// requirements. Extending it to cover spec 002 as well is a plausible future enhancement, but
/// doing so here, unasked, would create a bootstrapping oddity: a requirement-coverage gate
/// whose own specifying requirement has no test declaring that it covers it, since this file is
/// the first place such a declaration could go and nothing has added one yet. That question is
/// deliberately left for whichever later task decides to broaden scope, rather than settled by
/// implication here.
/// </para>
/// <para>
/// <b>Why two sibling test assemblies are loaded by file path rather than by project
/// reference.</b> Both <c>Identity.UnitTests</c> and <c>Identity.IntegrationTests</c> carry a
/// <c>ProjectReference</c> to this project (added so their test methods can use
/// <see cref="CoversRequirementAttribute"/> itself), so a <c>ProjectReference</c> in the other
/// direction would be circular. Instead, this gate loads their already-built output assemblies
/// directly with <see cref="Assembly.LoadFrom"/> from disk paths derived from the repository
/// root, which it locates the same way every other gate in this project does. Both projects
/// build to a <c>bin/&lt;Configuration&gt;/net10.0/</c> directory that mirrors this project's
/// own — including the active configuration, so a Release test run resolves Release-built
/// sibling assemblies rather than assuming Debug.
/// </para>
/// <para>
/// <b>A third source: this assembly itself.</b> Not every declaration lives in one of the two
/// sibling test projects — this project's own <c>CapabilityBoundaryGates</c> carries
/// <c>[CoversRequirement("FR-023")]</c> and <c>[CoversRequirement("FR-024")]</c> declarations,
/// because those two requirements are properties of the dependency graph that only a test
/// living in <c>ArchitectureTests</c> itself can check. This gate therefore also reflects over
/// <see cref="Assembly.GetExecutingAssembly"/> directly (no file-path loading needed, since it is
/// already loaded) so a declaration placed here is not mistaken for missing coverage.
/// </para>
/// </remarks>
public sealed class RequirementCoverageGates
{
    private const int ExpectedRequirementCount = 26;

    private static readonly Regex Spec001FrHeadingPattern = new(
        pattern: @"^-\s+\*\*(FR-0\d\d)\*\*:",
        options: RegexOptions.Compiled | RegexOptions.Multiline);

    private static readonly Lazy<IReadOnlyCollection<DeclaredCoverage>> DeclaredCoverages =
        new(ScanDeclaredCoverages);

    private static readonly Lazy<IReadOnlyCollection<string>> ValidSpec001RequirementIds =
        new(ScanValidSpec001RequirementIds);

    [CoversRequirement("FR-020")]
    [CoversRequirement("FR-021")]
    [Fact]
    public void EverySpec001Requirement_HasAtLeastOneDeclaringTest()
    {
        var declaredIds = DeclaredCoverages.Value
            .Select(coverage => coverage.RequirementId)
            .ToHashSet();

        var missing = ValidSpec001RequirementIds.Value
            .Where(requirementId => !declaredIds.Contains(requirementId))
            .OrderBy(requirementId => requirementId)
            .ToArray();

        missing.Should().BeEmpty(
            "every functional requirement in spec 001 must have at least one test carrying " +
            $"[CoversRequirement(\"FR-0NN\")], but no declaring test remains for: " +
            $"{string.Join(", ", missing)}");
    }

    [CoversRequirement("FR-022")]
    [Fact]
    public void NoDeclaration_NamesARequirementIdentifierAbsentFromSpec001()
    {
        var validIds = ValidSpec001RequirementIds.Value;

        var bogusDeclarations = DeclaredCoverages.Value
            .Where(coverage => !validIds.Contains(coverage.RequirementId))
            .ToArray();

        bogusDeclarations.Should().BeEmpty(
            "every [CoversRequirement] declaration must name an identifier that actually " +
            "exists in spec 001, but the following declarations do not: " +
            string.Join(", ", bogusDeclarations.Select(coverage =>
                $"\"{coverage.RequirementId}\" on {coverage.AssemblyName}!" +
                $"{coverage.DeclaringType}.{coverage.MethodName}")));
    }

    [Fact]
    public void ValidSpec001RequirementSet_HasExactlyTwentySixEntries()
    {
        // Guards the scan itself: if spec.md's heading format ever drifts in a way the regex
        // no longer matches, this fails loudly here rather than letting the two gates above
        // silently pass against an empty or truncated valid set.
        ValidSpec001RequirementIds.Value.Should().HaveCount(ExpectedRequirementCount,
            "spec 001 is expected to define exactly twenty-six functional requirements; a " +
            "different count means the heading scan is no longer matching spec.md correctly");
    }

    private static IReadOnlyCollection<string> ScanValidSpec001RequirementIds()
    {
        var repoRoot = ProjectFile.GetRepoRoot();
        var specPath = Path.Combine(
            repoRoot, "specs", "001-auth-tenant-management", "spec.md");

        var text = File.ReadAllText(specPath);

        return Spec001FrHeadingPattern
            .Matches(text)
            .Select(match => match.Groups[1].Value)
            .Distinct()
            .ToArray();
    }

    private static IReadOnlyCollection<DeclaredCoverage> ScanDeclaredCoverages()
    {
        var repoRoot = ProjectFile.GetRepoRoot();
        var configuration = new DirectoryInfo(AppContext.BaseDirectory).Parent!.Name;
        var frameworkFolderName = new DirectoryInfo(AppContext.BaseDirectory).Name;

        var assemblyPaths = new[]
        {
            Path.Combine(repoRoot, "tests", "Identity.UnitTests", "bin", configuration,
                frameworkFolderName, "Identity.UnitTests.dll"),
            Path.Combine(repoRoot, "tests", "Identity.IntegrationTests", "bin", configuration,
                frameworkFolderName, "Identity.IntegrationTests.dll"),
        };

        var coverages = new List<DeclaredCoverage>();

        var assemblies = new List<Assembly> { Assembly.GetExecutingAssembly() };

        foreach (var assemblyPath in assemblyPaths)
        {
            if (!File.Exists(assemblyPath))
            {
                throw new InvalidOperationException(
                    $"Expected to find a built test assembly at {assemblyPath}, but it does " +
                    "not exist. Build the whole solution (or at least " +
                    "Identity.UnitTests and Identity.IntegrationTests) before running this gate.");
            }

            assemblies.Add(Assembly.LoadFrom(assemblyPath));
        }

        foreach (var assembly in assemblies)
        {
            foreach (var type in assembly.GetTypes())
            {
                foreach (var method in type.GetMethods(
                    BindingFlags.Public | BindingFlags.Instance | BindingFlags.Static))
                {
                    foreach (var attribute in method.GetCustomAttributes<CoversRequirementAttribute>())
                    {
                        coverages.Add(new DeclaredCoverage(
                            attribute.RequirementId,
                            assembly.GetName().Name ?? assembly.Location,
                            type.FullName ?? type.Name,
                            method.Name));
                    }
                }
            }
        }

        return coverages;
    }

    private sealed record DeclaredCoverage(
        string RequirementId,
        string AssemblyName,
        string DeclaringType,
        string MethodName);
}
