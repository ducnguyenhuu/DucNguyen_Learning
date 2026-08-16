namespace ArchitectureTests.Support;

/// <summary>
/// Locates the repository root by walking up from the test assembly's output directory,
/// identifying the root by the presence of src/Tenancy. Exposed publicly so callers that
/// need to scan directories under the repo root directly (rather than through a project-name
/// lookup) don't have to duplicate this walk themselves.
/// </summary>
public static class RepoRoot
{
    /// <summary>
    /// Walks up from the test assembly's output directory to find the repository root,
    /// identified by the presence of src/Tenancy.
    /// </summary>
    public static string Find()
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
