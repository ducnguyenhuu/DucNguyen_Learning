using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using ArchitectureTests.Support;
using AwesomeAssertions;
using Xunit;

namespace ArchitectureTests;

/// <summary>
/// Two independent guards over this slice's telemetry story: no vendor-specific telemetry
/// SDK/agent package is referenced (ADR-011/ADR-018 restrict telemetry to OTLP-only), and no
/// metric recorded by the application carries a tenant or user identity tag (a metric tagged
/// with <c>tenant.id</c>/<c>user.id</c> turns a low-cardinality aggregate signal into an
/// unbounded-cardinality one and risks leaking tenant identity into a telemetry backend that,
/// unlike the application database, has no tenant query filter).
/// </summary>
/// <remarks>
/// <para>
/// <b>T017 — vendor SDK gate mirrors <c>DependencyPinGates</c>' provider-SDK check.</b> Reuses
/// <see cref="ProjectFile.GetCentralPackageVersions"/> rather than re-parsing
/// <c>Directory.Packages.props</c>, and matches package names against a small, illustrative
/// pattern list rather than an exhaustive one — same shape as
/// <c>DependencyPinGates.PinnedPackageNames_ContainNoKnownProviderSdkNamePattern</c>, applied to
/// telemetry vendors instead of AI providers. <c>ApplicationInsights</c> is included deliberately:
/// Application Insights' own SDK (not the generic-sounding name) would violate the OTLP-only
/// telemetry rule just as directly as a New Relic or Datadog agent would, even though it is a
/// Microsoft product. The patterns are chosen narrowly enough that they do not match any
/// already-approved package in the solution — in particular
/// <c>OpenTelemetry.Exporter.OpenTelemetryProtocol</c> and the other <c>OpenTelemetry.*</c>
/// packages, which are the one telemetry SDK this codebase is allowed to reference.
/// </para>
/// <para>
/// <b>T018 — metric-tenant-tag gate is a text scan, following <c>RawSqlGates</c>'
/// documented-limitations style.</b> This slice's own metric-recording surface is minimal today:
/// auto-instrumentation (added in a later task) emits ASP.NET Core's and SqlClient's own built-in
/// metrics, which carry route/status/command-type tags, not tenant or user identity. So this gate
/// is expected to pass vacuously for now — that is the correct, intended state, not a sign the
/// gate does nothing. It scans source files for a metrics-recording call (<c>Meter.CreateCounter</c>,
/// <c>CreateHistogram</c>, <c>CreateUpDownCounter</c>, or an instrument's <c>.Add(</c>/<c>.Record(</c>
/// call) and, independently, for a string literal tag key that looks like a tenant or user
/// identity key (<c>tenant.id</c>, <c>tenant_id</c>, <c>user.id</c>, <c>user_id</c>, case
/// insensitive). A violation is a file where both kinds of match occur within a small line
/// window of each other — a proxy for "this tag key is probably an argument to this call," not
/// a guarantee of it.
/// </para>
/// <para>
/// <b>T018's known limits.</b> Like <c>RawSqlGates</c>, this is line/window text matching, not a
/// syntax-tree analysis: it has no notion of which method call a string literal is actually an
/// argument to. It can produce a false positive if an unrelated tenant/user-id literal (e.g. a
/// log message) happens to sit within the line window of an unrelated metrics call in the same
/// file, and a false negative if the tag key is built from a non-literal expression (a constant,
/// a format string, string concatenation) rather than written as a literal, or if the call and
/// the literal are farther apart than the window (e.g. the tag dictionary is built up over many
/// lines). If either limitation ever matters in practice, the fix is a Roslyn syntax-tree
/// analyzer that resolves the actual arguments passed to the instrument call, not a looser or
/// wider regex/window.
/// </para>
/// </remarks>
public sealed class TelemetryVendorGates
{
    // Naming patterns that would identify a known telemetry vendor SDK/agent package if one
    // were ever pinned. Deliberately a small, illustrative set (mirrors DependencyPinGates'
    // KnownProviderSdkNamePatterns), not an exhaustive deny-list. None of these overlap with any
    // package name already in Directory.Packages.props — in particular, "ApplicationInsights"
    // does not match "OpenTelemetry.*", "Microsoft.Extensions.*", or
    // "AspNetCore.HealthChecks.*".
    private static readonly string[] KnownTelemetryVendorSdkNamePatterns =
    {
        "NewRelic",
        "Datadog",
        "Dynatrace",
        "ApplicationInsights",
    };

    // Matches a metrics-recording call site: creating an instrument, or recording a value on
    // one. Text-based, so a call reached through a local alias or split unusually across lines
    // may not match — see the class remarks.
    private static readonly Regex MetricRecordingCallPattern = new(
        pattern: @"\b(CreateCounter|CreateHistogram|CreateUpDownCounter)\s*[<(]|\.(Add|Record)\s*\(",
        options: RegexOptions.Compiled);

    // Matches a string literal that looks like a tenant or user identity tag key.
    private static readonly Regex TenantOrUserIdentityTagLiteralPattern = new(
        pattern: "\"(tenant\\.id|tenant_id|user\\.id|user_id)\"",
        options: RegexOptions.Compiled | RegexOptions.IgnoreCase);

    // How many lines apart a metrics-recording call and a tenant/user tag literal may be while
    // still being treated as "probably the same call" — see the class remarks on this being a
    // proxy, not a guarantee.
    private const int ProximityWindowLines = 3;

    [Fact]
    public void PackageVersions_ContainNoKnownTelemetryVendorSdkNamePattern()
    {
        var packages = ProjectFile.GetCentralPackageVersions();

        var matches = packages
            .SelectMany(package => KnownTelemetryVendorSdkNamePatterns
                .Where(pattern => package.Name.Contains(pattern, StringComparison.OrdinalIgnoreCase))
                .Select(pattern => $"{package.Name} (matched pattern \"{pattern}\")"))
            .ToArray();

        matches.Should().BeEmpty(
            "ADR-011/ADR-018 restrict telemetry to OTLP-only — Directory.Packages.props must not " +
            "reference a vendor-specific telemetry SDK/agent package (e.g. New Relic, Datadog, " +
            "Dynatrace, or Application Insights' own SDK). Matched: " + string.Join(", ", matches));
    }

    [Fact]
    public void NoMetricRecordingCallIsFoundNearATenantOrUserIdentityTagLiteral()
    {
        var repoRoot = ProjectFile.GetRepoRoot();
        var sourceRoot = Path.Combine(repoRoot, "src");

        var violations = FindTenantOrUserTaggedMetricCalls(sourceRoot, repoRoot).ToArray();

        violations.Should().BeEmpty(
            "a metric recorded by the application must never carry a tenant.id/user.id tag — " +
            "doing so turns a low-cardinality aggregate signal into an unbounded-cardinality one " +
            "and risks leaking tenant identity into a telemetry backend that has no tenant query " +
            "filter. This is a text-based proximity scan (see TelemetryVendorGates' class " +
            "remarks for its known limits), not a semantic one. Found: " +
            string.Join(", ", violations));
    }

    private static IEnumerable<string> FindTenantOrUserTaggedMetricCalls(
        string sourceRoot,
        string repoRoot)
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
            var lines = File.ReadAllLines(filePath);
            var relativePath = Path.GetRelativePath(repoRoot, filePath).Replace('\\', '/');

            var callLines = Enumerable.Range(0, lines.Length)
                .Where(i => MetricRecordingCallPattern.IsMatch(lines[i]))
                .ToArray();
            var tagLines = Enumerable.Range(0, lines.Length)
                .Where(i => TenantOrUserIdentityTagLiteralPattern.IsMatch(lines[i]))
                .ToArray();

            if (callLines.Length == 0 || tagLines.Length == 0)
            {
                continue;
            }

            foreach (var tagLine in tagLines)
            {
                var nearbyCall = callLines
                    .Where(callLine => Math.Abs(callLine - tagLine) <= ProximityWindowLines)
                    .Select(callLine => callLine)
                    .Cast<int?>()
                    .FirstOrDefault();

                if (nearbyCall is not null)
                {
                    yield return $"{relativePath}:{tagLine + 1} (near metrics call at line " +
                        $"{nearbyCall.Value + 1})";
                }
            }
        }
    }

    private static bool IsUnderExcludedDirectory(string path)
    {
        var segments = path.Split(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);

        return segments.Any(segment => segment is "bin" or "obj" or ".git");
    }
}
