using System.IO;
using System.Linq;
using ArchitectureTests.Support;
using AwesomeAssertions;
using Xunit;

namespace ArchitectureTests;

/// <summary>
/// FR-023/FR-024 coverage (T089 gap closure): structural (project-reference-graph) evidence that
/// the tenancy capability owns its data exclusively and that the domain layer has no dependency
/// on infrastructure.
/// </summary>
/// <remarks>
/// <para>
/// <b>Why a structural test rather than a runtime one.</b> FR-023 ("no other capability may read
/// or write [tenancy's] data other than through its published interface") and FR-024 ("the
/// domain layer MUST NOT depend on infrastructure concerns") are both properties of the
/// <em>dependency graph</em>, not of any runtime behavior — there is nothing to invoke that would
/// distinguish a compliant graph from a non-compliant one at runtime. Automated enforcement of
/// architectural boundaries in general is explicitly deferred to S3 (spec.md's Deferred
/// Requirements table, <c>old-FR-028</c>), but this test reads the actual <c>.csproj</c> files
/// checked into source control today, so it fails the moment a genuine violation is committed —
/// without waiting for S3's dedicated tooling.
/// </para>
/// <para>
/// <b>Why this closes a real gap rather than restating FR-024's existing manual-inspection
/// note.</b> Before this test, FR-023/FR-024 compliance was verifiable only by a human reading
/// <c>.csproj</c> files by hand (as done once for the coverage matrix this test accompanies). This
/// test makes that same check automated and repeatable.
/// </para>
/// <para>
/// FR-023 also depends on there being no *second* capability yet that could read/write tenancy's
/// data directly — today <c>src/</c> contains only the <c>Tenancy.*</c> projects, so the
/// strongest available proof is that nothing outside the <c>Tenancy.*</c> project set exists at
/// all, and that within it, only <c>Tenancy.Api</c> (the composition root / published interface)
/// references <c>Tenancy.Infrastructure</c> directly.
/// </para>
/// </remarks>
public sealed class CapabilityBoundaryGates
{
    private static readonly string RepoRoot = ProjectFile.GetRepoRoot();

    [Fact]
    public void TenancyDomain_HasNoProjectReferences()
    {
        var references = ProjectFile.GetProjectReferences("Tenancy.Domain");

        references.Should().BeEmpty(
            "FR-024 requires the domain layer to depend on nothing, least of all infrastructure — " +
            "Tenancy.Domain.csproj must have zero <ProjectReference> entries.");
    }

    [Fact]
    public void TenancyApplication_OnlyReferencesDomain()
    {
        var references = ProjectFile.GetProjectReferences("Tenancy.Application");

        references.Should().BeEquivalentTo(
            new[] { "Tenancy.Domain" },
            "FR-024 requires the application layer to depend inward only on the domain, never on " +
            "infrastructure.");
    }

    [Fact]
    public void TenancyInfrastructure_NeverReferencedByDomainOrApplication()
    {
        ProjectFile.GetProjectReferences("Tenancy.Domain").Should().NotContain("Tenancy.Infrastructure");
        ProjectFile.GetProjectReferences("Tenancy.Application").Should().NotContain("Tenancy.Infrastructure");
    }

    [Fact]
    public void OnlyTenancyApi_ReferencesInfrastructureDirectly()
    {
        // FR-023: the composition root (Tenancy.Api) is the tenancy capability's published
        // interface boundary. If any project other than Tenancy.Api referenced
        // Tenancy.Infrastructure directly, that project would be reaching straight past the
        // published interface into the capability's own persistence internals.
        var csprojFiles = Directory.GetFiles(
            Path.Combine(RepoRoot, "src"),
            "*.csproj",
            SearchOption.AllDirectories);

        var referencersOfInfrastructure = csprojFiles
            .Where(path => !string.Equals(Path.GetFileNameWithoutExtension(path), "Tenancy.Infrastructure", StringComparison.Ordinal))
            .Where(path => ProjectFile.GetProjectReferences(new FileInfo(path)).Contains("Tenancy.Infrastructure"))
            .Select(path => Path.GetFileNameWithoutExtension(path)!)
            .ToArray();

        referencersOfInfrastructure.Should().BeEquivalentTo(
            new[] { "Tenancy.Api" },
            "FR-023 requires that nothing but the capability's own composition root/published " +
            "interface (Tenancy.Api) reaches directly into Tenancy.Infrastructure's persistence " +
            "internals.");
    }

    [Fact]
    public void NoCapabilityOtherThanTenancyExistsUnderSrc()
    {
        // FR-023 is only observable once a second capability exists to (not) violate the
        // boundary against. Today there is none — this test pins that fact down explicitly so a
        // future capability added under src/ is a deliberate, visible decision (and a reminder to
        // extend this suite with a real cross-capability-access check at that point) rather than
        // a silent scope creep.
        var srcDirectories = Directory.GetDirectories(Path.Combine(RepoRoot, "src"));

        srcDirectories.Select(path => Path.GetFileName(path)!).Should().BeEquivalentTo(
            new[] { "Tenancy" },
            "this is a documented snapshot, not an enforced rule: spec.md's slice S2 " +
            "deliberately contains exactly one capability. If this fails because a second " +
            "capability was legitimately added, update this expectation and add a real " +
            "cross-capability-access test for FR-023 alongside it — don't just delete this test.");
    }
}
