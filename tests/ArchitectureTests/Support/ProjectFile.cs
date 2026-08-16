using System.Xml.Linq;

namespace ArchitectureTests.Support;

/// <summary>
/// A single &lt;PackageReference&gt; or &lt;PackageVersion&gt; entry read from a project file or
/// from Directory.Packages.props. Version is null when the source element omitted it (e.g. a
/// bare PackageReference under central package management).
/// </summary>
public sealed record PackageReference(string Name, string? Version);

/// <summary>
/// Reads project- and package-reference declarations out of the .csproj files under src/ and out
/// of the repo's centrally managed Directory.Packages.props, so every architecture gate can
/// answer "what does this project depend on" without re-parsing MSBuild XML itself.
/// </summary>
public static class ProjectFile
{
    public static string[] GetProjectReferences(string projectName)
    {
        var csprojPath = FindCsproj(projectName);

        return GetProjectReferences(csprojPath);
    }

    public static string[] GetProjectReferences(FileInfo csprojPath)
    {
        var document = XDocument.Load(csprojPath.FullName);

        return document
            .Descendants("ProjectReference")
            .Select(element => element.Attribute("Include")!.Value.Replace('\\', '/'))
            .Select(path => Path.GetFileNameWithoutExtension(path)!)
            .ToArray();
    }

    public static PackageReference[] GetPackageReferences(string projectName)
    {
        var csprojPath = FindCsproj(projectName);

        return GetPackageReferences(csprojPath);
    }

    public static PackageReference[] GetPackageReferences(FileInfo csprojPath)
    {
        var document = XDocument.Load(csprojPath.FullName);

        return document
            .Descendants("PackageReference")
            .Select(element => new PackageReference(
                element.Attribute("Include")!.Value,
                element.Attribute("Version")?.Value))
            .ToArray();
    }

    /// <summary>
    /// Reads the complete, centrally managed package list from Directory.Packages.props at the
    /// repo root. Central package management means individual .csproj PackageReference entries
    /// usually omit a version, so this is the one place a package's pinned version can actually
    /// be found.
    /// </summary>
    public static PackageReference[] GetCentralPackageVersions()
    {
        var propsPath = Path.Combine(FindRepoRoot(), "Directory.Packages.props");
        var document = XDocument.Load(propsPath);

        return document
            .Descendants("PackageVersion")
            .Select(element => new PackageReference(
                element.Attribute("Include")!.Value,
                element.Attribute("Version")?.Value))
            .ToArray();
    }

    private static FileInfo FindCsproj(string projectName)
    {
        var path = Directory.GetFiles(
                Path.Combine(FindRepoRoot(), "src"),
                $"{projectName}.csproj",
                SearchOption.AllDirectories)
            .Single();

        return new FileInfo(path);
    }

    private static string FindRepoRoot()
    {
        var directory = new DirectoryInfo(AppContext.BaseDirectory);

        while (directory is not null)
        {
            if (Directory.Exists(Path.Combine(directory.FullName, "src", "Tenancy")))
            {
                return directory.FullName;
            }

            directory = directory.Parent;
        }

        throw new InvalidOperationException(
            "Could not locate repository root (a directory containing src/Tenancy) by walking " +
            $"up from {AppContext.BaseDirectory}.");
    }
}
