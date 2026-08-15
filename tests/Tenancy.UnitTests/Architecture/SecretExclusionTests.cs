using System.IO;
using System.Linq;
using System.Xml.Linq;
using AwesomeAssertions;
using Xunit;

namespace Tenancy.UnitTests.Architecture;

/// <summary>
/// FR-026 coverage (T089 gap closure): proves the repository's checked-in secret-exclusion
/// mechanism actually exists and actually covers the patterns local development secrets would use
/// — not that no secret has ever been committed (that is a whole-history scan, explicitly a
/// manual, one-time step per <c>specs/001-auth-tenant-management/tasks.md</c>'s T092, not an
/// automated-suite concern) or that a CI gate blocks new ones (no such gate exists in this repo
/// yet — see this task's coverage report for that gap).
/// </summary>
/// <remarks>
/// This is deliberately narrow: it asserts the *mechanism* FR-026's second sentence requires
/// ("Local development secrets MUST use a mechanism excluded from version control") is present
/// and structurally correct, which is the part of FR-026 an automated unit test can meaningfully
/// prove without a full-history secret scan.
/// </remarks>
public sealed class SecretExclusionTests
{
    private static readonly string RepoRoot = FindRepoRoot();

    [Theory]
    [InlineData("*.env")]
    [InlineData(".env.*")]
    [InlineData("appsettings.Development.json")]
    [InlineData("appsettings.Local.json")]
    [InlineData("secrets.json")]
    [InlineData("*.pfx")]
    [InlineData("*.p12")]
    public void GitIgnore_ExcludesLocalSecretPattern(string pattern)
    {
        var gitIgnoreLines = File.ReadAllLines(Path.Combine(RepoRoot, ".gitignore"));

        gitIgnoreLines.Should().Contain(
            pattern,
            $"FR-026 requires local development secrets to use a mechanism excluded from " +
            $"version control; .gitignore must exclude the '{pattern}' pattern.");
    }

    [Fact]
    public void TenancyApi_HasUserSecretsIdConfigured()
    {
        // The dotnet user-secrets mechanism (secrets stored outside the repo entirely, under the
        // user profile, keyed by this id) is this project's actual "mechanism excluded from
        // version control" for local development secrets — not merely a gitignored file that a
        // developer could still accidentally `git add -f`.
        var csprojPath = Directory.GetFiles(
                Path.Combine(RepoRoot, "src"),
                "Tenancy.Api.csproj",
                SearchOption.AllDirectories)
            .Single();

        var document = XDocument.Load(csprojPath);
        var userSecretsId = document.Descendants("UserSecretsId").SingleOrDefault()?.Value;

        userSecretsId.Should().NotBeNullOrWhiteSpace(
            "FR-026 requires a real, version-control-excluded local-secrets mechanism; " +
            "Tenancy.Api.csproj must configure a UserSecretsId for the dotnet user-secrets tool.");
    }

    [Fact]
    public void AppsettingsJson_CommittedToSourceControl_ContainsNoConnectionStringWithCredentials()
    {
        // The one appsettings*.json file that IS committed (appsettings.json itself — the
        // Development/Local variants are gitignored per the Theory test above) must not contain
        // an embedded username/password-style connection string.
        var appsettingsPath = Directory.GetFiles(
                Path.Combine(RepoRoot, "src"),
                "appsettings.json",
                SearchOption.AllDirectories)
            .FirstOrDefault();

        if (appsettingsPath is null)
        {
            return;
        }

        var content = File.ReadAllText(appsettingsPath);

        foreach (var forbiddenFragment in new[] { "Password=", "pwd=", "User Id=" })
        {
            content.Should().NotContain(
                forbiddenFragment,
                "FR-026 forbids committing any connection string containing a secret; the " +
                "checked-in appsettings.json must not embed credentials.");
        }
    }

    private static string FindRepoRoot()
    {
        var directory = new DirectoryInfo(AppContext.BaseDirectory);

        while (directory is not null)
        {
            if (File.Exists(Path.Combine(directory.FullName, ".gitignore"))
                && Directory.Exists(Path.Combine(directory.FullName, "src", "Tenancy")))
            {
                return directory.FullName;
            }

            directory = directory.Parent;
        }

        throw new InvalidOperationException(
            "Could not locate repository root (a directory containing .gitignore and " +
            $"src/Tenancy) by walking up from {AppContext.BaseDirectory}.");
    }
}
