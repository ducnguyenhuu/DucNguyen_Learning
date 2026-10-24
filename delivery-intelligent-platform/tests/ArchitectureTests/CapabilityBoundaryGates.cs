using System.IO;
using System.Linq;
using ArchitectureTests.Support;
using AwesomeAssertions;
using Xunit;

namespace ArchitectureTests;

/// <summary>
/// Structural (project-reference-graph) evidence that the tenancy capability owns its data
/// exclusively and that the domain layer has no dependency on infrastructure.
/// </summary>
/// <remarks>
/// <para>
/// <b>Why a structural test rather than a runtime one.</b> "No other capability may read or
/// write tenancy's data other than through its published interface" and "the domain layer must
/// not depend on infrastructure concerns" are both properties of the <em>dependency graph</em>,
/// not of any runtime behavior — there is nothing to invoke that would distinguish a compliant
/// graph from a non-compliant one at runtime. General automated enforcement of architectural
/// boundaries is explicitly deferred to a later roadmap slice, but this test reads the actual
/// <c>.csproj</c> files checked into source control today, so it fails the moment a genuine
/// violation is committed — without waiting for that dedicated tooling.
/// </para>
/// <para>
/// <b>Why this closes a real gap rather than restating an existing manual-inspection note.</b>
/// Before this test, this boundary was verifiable only by a human reading <c>.csproj</c> files by
/// hand. This test makes that same check automated and repeatable.
/// </para>
/// <para>
/// The exclusive-ownership property above also depends on there being no *second* capability yet
/// that could read/write tenancy's data directly — today <c>src/</c> contains only the
/// <c>Identity.*</c> projects, so the strongest available proof is that nothing outside the
/// <c>Identity.*</c> project set exists at all, and that within it, only <c>Identity.Api</c> (the
/// composition root / published interface) references <c>Identity.Infrastructure</c> directly.
/// </para>
/// </remarks>
public sealed class CapabilityBoundaryGates
{
    private static readonly string RepoRoot = ProjectFile.GetRepoRoot();

    [CoversRequirement("FR-024")]
    [Fact]
    public void IdentityDomain_HasNoProjectReferences()
    {
        var references = ProjectFile.GetProjectReferences("Identity.Domain");

        references.Should().BeEmpty(
            "the domain layer must depend on nothing, least of all infrastructure — " +
            "Identity.Domain.csproj must have zero <ProjectReference> entries.");
    }

    [CoversRequirement("FR-024")]
    [Fact]
    public void IdentityApplication_OnlyReferencesDomain()
    {
        var references = ProjectFile.GetProjectReferences("Identity.Application");

        references.Should().BeEquivalentTo(
            new[] { "Identity.Domain" },
            "the application layer must depend inward only on the domain, never on " +
            "infrastructure.");
    }

    [CoversRequirement("FR-024")]
    [Fact]
    public void IdentityInfrastructure_NeverReferencedByDomainOrApplication()
    {
        ProjectFile.GetProjectReferences("Identity.Domain").Should().NotContain("Identity.Infrastructure");
        ProjectFile.GetProjectReferences("Identity.Application").Should().NotContain("Identity.Infrastructure");
    }

    [CoversRequirement("FR-023")]
    [Fact]
    public void OnlyIdentityApi_ReferencesInfrastructureDirectly()
    {
        // The composition root (Identity.Api) is the tenancy capability's published interface
        // boundary. If any project other than Identity.Api referenced Identity.Infrastructure
        // directly, that project would be reaching straight past the published interface into
        // the capability's own persistence internals.
        var csprojFiles = Directory.GetFiles(
            Path.Combine(RepoRoot, "src"),
            "*.csproj",
            SearchOption.AllDirectories);

        var referencersOfInfrastructure = csprojFiles
            .Where(path => !string.Equals(Path.GetFileNameWithoutExtension(path), "Identity.Infrastructure", StringComparison.Ordinal))
            .Where(path => ProjectFile.GetProjectReferences(new FileInfo(path)).Contains("Identity.Infrastructure"))
            .Select(path => Path.GetFileNameWithoutExtension(path)!)
            .ToArray();

        referencersOfInfrastructure.Should().BeEquivalentTo(
            new[] { "Identity.Api" },
            "the capability's own composition root/published interface (Identity.Api) must be " +
            "the only project reaching directly into Identity.Infrastructure's persistence " +
            "internals.");
    }

    [Fact]
    public void NoProjectOutsideIdentityFamily_ReferencesIdentityInfrastructure()
    {
        // Generalizes the check above beyond "only Identity.Api": today the Identity.* family is
        // the only capability under src/, and within it, only Identity.Api touches
        // Identity.Infrastructure directly. This assertion states the broader property that
        // actually matters once a second capability exists: nothing outside the Identity.* family
        // — not just "nothing outside Identity.Api" — may reach into Identity.Infrastructure via a
        // project reference. Today it is vacuously true, since no non-Identity.* project exists at
        // all.
        var csprojFiles = Directory.GetFiles(
            Path.Combine(RepoRoot, "src"),
            "*.csproj",
            SearchOption.AllDirectories);

        var outsideFamilyReferencingInfrastructure = csprojFiles
            .Where(path => !Path.GetFileNameWithoutExtension(path)!.StartsWith("Identity.", StringComparison.Ordinal))
            .Where(path => ProjectFile.GetProjectReferences(new FileInfo(path)).Contains("Identity.Infrastructure"))
            .Select(path => Path.GetFileNameWithoutExtension(path)!)
            .ToArray();

        outsideFamilyReferencingInfrastructure.Should().BeEmpty(
            "no project outside the Identity.* family may reference Identity.Infrastructure by " +
            "project reference — only the capability's own composition root may reach into its " +
            "persistence internals.");
    }

    [Fact]
    public void NoSourceFileOutsideIdentityFamily_NamesIdentityDbContext()
    {
        // Defense in depth alongside the project-reference check above: since IdentityDbContext
        // lives in Identity.Infrastructure, naming it from outside the Identity.* family would
        // almost always require a project reference too — but a project-reference-graph check
        // alone would miss an indirect route such as reflection, a dynamically loaded assembly,
        // or a copy-pasted type name in a generated or partial file. This scans source text
        // directly for the literal identifier instead of relying on the reference graph.
        var repoRoot = RepoRoot;
        var sourceRoot = Path.Combine(repoRoot, "src");

        var offendingFiles = Directory
            .EnumerateFiles(sourceRoot, "*.cs", SearchOption.AllDirectories)
            .Where(path => !IsUnderIdentityFamily(path, sourceRoot))
            .Where(path => !IsUnderBuildOutputDirectory(path))
            .Where(path => File.ReadAllText(path).Contains("IdentityDbContext", StringComparison.Ordinal))
            .Select(path => Path.GetRelativePath(repoRoot, path).Replace('\\', '/'))
            .ToArray();

        offendingFiles.Should().BeEmpty(
            "no source file outside the Identity.* family may name the Identity.Infrastructure " +
            "type IdentityDbContext, even without a project reference — that would be an " +
            "indirect route (reflection, dynamic loading, a copy-pasted type name) around the " +
            "reference-graph check above.");
    }

    [CoversRequirement("FR-023")]
    [Fact]
    public void NoCapabilityOtherThanIdentityExistsUnderSrc()
    {
        // The cross-capability reference gates above are only observable once a second capability
        // exists to (not) violate the boundary against. Today there is none — this test pins that
        // fact down explicitly so a future capability added under src/ is a deliberate, visible
        // decision rather than a silent scope creep.
        var srcDirectories = Directory.GetDirectories(Path.Combine(RepoRoot, "src"));

        srcDirectories.Select(path => Path.GetFileName(path)!).Should().BeEquivalentTo(
            new[] { "Identity" },
            "this is a documented snapshot, not an enforced rule: spec.md's slice S2 " +
            "deliberately contains exactly one capability. If this fails because a second " +
            "capability was legitimately added, update this expectation and extend the " +
            "cross-capability reference gate above (the one confirming nothing outside " +
            "Identity.* touches Identity.Infrastructure or names IdentityDbContext) to cover the " +
            "new capability — don't just delete this test.");
    }

    private static bool IsUnderIdentityFamily(string filePath, string sourceRoot)
    {
        var relativePath = Path.GetRelativePath(sourceRoot, filePath);
        var topLevelSegment = relativePath.Split(
            Path.DirectorySeparatorChar,
            Path.AltDirectorySeparatorChar)[0];

        return topLevelSegment.StartsWith("Identity", StringComparison.Ordinal);
    }

    private static bool IsUnderBuildOutputDirectory(string filePath)
    {
        var segments = filePath.Split(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);

        return segments.Any(segment => segment is "bin" or "obj");
    }
}
