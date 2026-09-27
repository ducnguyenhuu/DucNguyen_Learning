using System.Text.RegularExpressions;
using ArchitectureTests.Support;
using AwesomeAssertions;
using Xunit;

namespace ArchitectureTests;

/// <summary>
/// Static gates over the tracked container configuration files this slice adds — the root
/// <c>Dockerfile</c>, <c>compose.yaml</c>, and <c>.env.example</c> — enforcing FR-002, FR-008,
/// and FR-011 as build-failing checks rather than something a reviewer has to remember to look
/// for (Principle VII). This is text scanning over a fixed, small file set, not a semantic
/// analysis: it does not build or run the image (see
/// <c>infrastructure/scripts/scan-image-secrets.sh</c> and
/// <c>infrastructure/scripts/scan-image-vulnerabilities.sh</c> for the checks that require an
/// actual built image).
/// </summary>
public sealed class ContainerConfigurationGates
{
    private static readonly string[] TrackedContainerConfigFiles =
    [
        "Dockerfile",
        "compose.yaml",
        ".env.example",
    ];

    // A credential literal: something that looks like an actual secret value, not a variable
    // name or a placeholder. Deliberately narrow — this does not try to catch every possible
    // secret shape, only the ones a `${VAR:?message}`-based file legitimately never contains:
    // a non-empty value assigned directly to a password/key/secret/token-shaped key.
    private static readonly Regex CredentialLiteralPattern = new(
        pattern: @"(?i)\b(password|pwd|secret|api[_-]?key|access[_-]?key|token)\s*[:=]\s*" +
                 @"[""']?(?!\$\{|\s*$)[^\s""'{][^\s""']*",
        options: RegexOptions.Compiled);

    private static readonly string[] AzureCredentialOrProductionInfraPatterns =
    [
        "kubectl",
        ".yaml.helm",
        "helm install",
        "helm upgrade",
        "docker push",
        "docker login",
        "azurecr.io",
        "az aks",
        "az login",
        "workload identity",
        "AZURE_CLIENT_SECRET",
        "AZURE_TENANT_SECRET",
    ];

    [Fact]
    public void TrackedContainerConfigFiles_ContainNoCredentialLiteral()
    {
        var repoRoot = ProjectFile.GetRepoRoot();

        var violations = TrackedContainerConfigFiles
            .Select(fileName => Path.Combine(repoRoot, fileName))
            .Where(File.Exists)
            .SelectMany(FindCredentialLiteralViolations)
            .ToArray();

        violations.Should().BeEmpty(
            "FR-008: the built image and tracked container configuration must contain no " +
            "secret, credential, access token, or connection-string value — every credential " +
            "must reach the stack via an untracked .env interpolated as ${VAR:?message}, never " +
            "a literal value in a tracked file. Found: " + string.Join(", ", violations));
    }

    [Fact]
    public void Dockerfile_SetsNonRootUser()
    {
        var repoRoot = ProjectFile.GetRepoRoot();
        var dockerfilePath = Path.Combine(repoRoot, "Dockerfile");

        File.Exists(dockerfilePath).Should().BeTrue(
            "the root Dockerfile is this slice's deliverable image (FR-001)");

        var lines = File.ReadAllLines(dockerfilePath);
        var userLines = lines.Where(line => line.TrimStart().StartsWith(
            "USER ", StringComparison.OrdinalIgnoreCase)).ToArray();

        userLines.Should().NotBeEmpty(
            "FR-002: the image must run as a non-root user — the Dockerfile must contain an " +
            "explicit USER instruction, even though the chiseled base already defaults to " +
            "$APP_UID, so a future base-image change cannot silently reintroduce root");

        userLines.Should().NotContain(
            line => Regex.IsMatch(line, @"(?i)USER\s+(root|0)\s*$"),
            "FR-002: the Dockerfile must never set USER to root or uid 0");
    }

    [Fact]
    public void TrackedContainerConfigFiles_ContainNoProductionInfrastructureReference()
    {
        var repoRoot = ProjectFile.GetRepoRoot();

        var violations = TrackedContainerConfigFiles
            .Select(fileName => Path.Combine(repoRoot, fileName))
            .Where(File.Exists)
            .SelectMany(FindProductionInfrastructureViolations)
            .ToArray();

        violations.Should().BeEmpty(
            "FR-011: the artifact and local instructions must remain deployable by later " +
            "infrastructure work without embedding Azure credentials, Kubernetes/Helm " +
            "manifests, registry publication, or pipeline logic — those are S6/S7 concerns, " +
            "out of scope for this slice's local Compose stack. Found: " +
            string.Join(", ", violations));
    }

    private static IEnumerable<string> FindCredentialLiteralViolations(string filePath)
    {
        var fileName = Path.GetFileName(filePath);

        foreach (var (line, index) in File.ReadLines(filePath).Select((line, index) => (line, index)))
        {
            // A `${VAR:?message}` or `${VAR}` interpolation, or a bare "KEY=" with an empty
            // right-hand side (.env.example's contract), is exactly what these files are
            // supposed to contain — only a literal, non-empty, non-interpolated value is a
            // violation.
            if (line.Contains("${", StringComparison.Ordinal))
            {
                continue;
            }

            var match = CredentialLiteralPattern.Match(line);
            if (match.Success)
            {
                yield return $"{fileName}:{index + 1}: \"{match.Value.Trim()}\"";
            }
        }
    }

    private static IEnumerable<string> FindProductionInfrastructureViolations(string filePath)
    {
        var fileName = Path.GetFileName(filePath);

        foreach (var (line, index) in File.ReadLines(filePath).Select((line, index) => (line, index)))
        {
            foreach (var pattern in AzureCredentialOrProductionInfraPatterns)
            {
                if (line.Contains(pattern, StringComparison.OrdinalIgnoreCase))
                {
                    yield return $"{fileName}:{index + 1}: matched \"{pattern}\"";
                }
            }
        }
    }
}
