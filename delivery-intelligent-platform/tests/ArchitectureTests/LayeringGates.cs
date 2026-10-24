using System.Linq;
using ArchitectureTests.Support;
using AwesomeAssertions;
using Xunit;

namespace ArchitectureTests;

/// <summary>
/// Enforces that the innermost layers of the identity capability — <c>Identity.Domain</c> and
/// <c>Identity.Application</c> — never take on a dependency on a specific infrastructure
/// technology (an ORM, a cloud SDK, or a web framework), regardless of whether that dependency
/// arrives as a NuGet package or as a reference to another project that itself carries the
/// technology in.
/// </summary>
/// <remarks>
/// <para>
/// <b>Why both reference kinds are checked.</b> The technologies this gate forbids
/// (Entity Framework Core, the Azure SDKs, ASP.NET Core) are all delivered as NuGet packages, so
/// a direct <c>&lt;PackageReference&gt;</c> is the reference kind that would actually catch a
/// real violation — this is exactly how <c>Identity.Application</c> once carried an EF Core
/// package reference before it was removed. The <c>&lt;ProjectReference&gt;</c> check exists as a
/// second line of defense: nothing under <c>src/Identity</c> is itself named after a forbidden
/// technology today, but if a future internal project acted as a thin wrapper around one of these
/// technologies, a project reference to it would smuggle the same violation in indirectly. Both
/// checks together mean the gate does not depend on assuming how the dependency would arrive.
/// </para>
/// <para>
/// <b>Why prefix matching, not exact matching.</b> The forbidden set is really "no EF Core at
/// all", "no Azure SDK at all", and "no ASP.NET Core at all" — not "no dependency on exactly the
/// package named <c>Microsoft.EntityFrameworkCore</c>, but its provider and tooling packages
/// (<c>Microsoft.EntityFrameworkCore.SqlServer</c>, <c>Microsoft.EntityFrameworkCore.Design</c>,
/// and so on) are fine." An exact-match gate would have let those sibling packages straight
/// through. Matching on a name prefix closes that gap for all three technologies, including the
/// ones already written with a trailing dot in the requirement text (<c>Azure.*</c>,
/// <c>Microsoft.AspNetCore.*</c>).
/// </para>
/// </remarks>
public sealed class LayeringGates
{
    private static readonly string[] ForbiddenPackagePrefixes =
    {
        "Microsoft.EntityFrameworkCore",
        "Azure.",
        "Microsoft.AspNetCore.",
    };

    [Fact]
    public void IdentityDomain_DoesNotReferenceForbiddenTechnology()
    {
        AssertNoForbiddenReferences("Identity.Domain");
    }

    [Fact]
    public void IdentityApplication_DoesNotReferenceForbiddenTechnology()
    {
        AssertNoForbiddenReferences("Identity.Application");
    }

    private static void AssertNoForbiddenReferences(string projectName)
    {
        var offendingPackages = ProjectFile.GetPackageReferences(projectName)
            .Where(reference => ForbiddenPackagePrefixes.Any(
                prefix => reference.Name.StartsWith(prefix, StringComparison.Ordinal)))
            .Select(reference => reference.Name)
            .ToArray();

        offendingPackages.Should().BeEmpty(
            $"{projectName} must not depend on EF Core, an Azure SDK, or ASP.NET Core via a " +
            $"<PackageReference> — found: {(offendingPackages.Length == 0 ? "(none)" : string.Join(", ", offendingPackages))}");

        var offendingProjects = ProjectFile.GetProjectReferences(projectName)
            .Where(referencedProject => ForbiddenPackagePrefixes.Any(
                prefix => referencedProject.Contains(prefix.TrimEnd('.'), StringComparison.Ordinal)))
            .ToArray();

        offendingProjects.Should().BeEmpty(
            $"{projectName} must not depend on EF Core, an Azure SDK, or ASP.NET Core via a " +
            $"<ProjectReference> to a project that itself carries the technology in its name — " +
            $"found: {(offendingProjects.Length == 0 ? "(none)" : string.Join(", ", offendingProjects))}");
    }
}
