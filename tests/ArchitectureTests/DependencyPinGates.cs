using System.IO;
using System.Linq;
using ArchitectureTests.Support;
using AwesomeAssertions;
using Xunit;

namespace ArchitectureTests;

/// <summary>
/// A checked-in pin of every package name in the solution's centrally managed version list, so a
/// wholly new (or removed) package is a visible, deliberate diff against this file rather than a
/// silent addition to <c>Directory.Packages.props</c>. One pin catches several forbidden
/// dependency categories at once — a provider SDK, a validation library, a mediator/dispatcher
/// (ADR-021 rulings 1 and 2) — because all of them would show up the same way: a new package name
/// that was not there before.
/// </summary>
/// <remarks>
/// <para>
/// <b>Names only, not versions.</b> The pin asserts the actual package set matches the checked-in
/// set of names, unordered — it deliberately does not assert exact versions. A version bump
/// (e.g. <c>10.0.10</c> to <c>10.0.11</c>) is routine maintenance, not "a new package was added";
/// pinning exact versions would make this gate fail on every patch update, which is noise, not
/// signal. What must not happen silently is a package appearing or disappearing from the list —
/// that is what the pin actually guards.
/// </para>
/// <para>
/// <b>Where the pin lives and how to update it.</b> The pin is the checked-in
/// <see cref="PinnedPackageNames"/> array below, inline in this file — not a separate config
/// file. This matches <c>RawSqlGates</c>' allow-list precedent of keeping a gate and its pin
/// together in one file: one source of truth, no second file to remember to update. Adding a
/// legitimate new package means updating BOTH <c>Directory.Packages.props</c> (the actual
/// reference the build uses) AND <see cref="PinnedPackageNames"/> in this file, in the same PR —
/// the failure message below says this explicitly, so the first person who hits this gate updates
/// the pin rather than deleting the test.
/// </para>
/// <para>
/// <b>Scope: the whole solution, not just <c>src/</c> — and why that's unavoidable.</b>
/// <c>Directory.Packages.props</c> is solution-wide: every project, under both <c>src/</c> and
/// <c>tests/</c>, draws its versions from the same central list, and central package management
/// has no way to scope a <c>PackageVersion</c> entry to "only usable from <c>src/</c>" — which
/// project actually references a package is a separate, per-project decision already governed by
/// each project's own <c>&lt;PackageReference&gt;</c> list, not by this file. There is no
/// separate <c>src/</c>-only manifest to pin instead. So this pin's scope is unavoidably the
/// whole solution's centrally managed package set, which means it also catches additions of
/// test-only packages (e.g. a new mocking library alongside <c>xunit.v3</c>,
/// <c>Testcontainers.MsSql</c>, and <c>AwesomeAssertions</c>) even though the gate's headline
/// motivating case is "no provider SDK in production code." This is an accepted, intentional
/// consequence, not an oversight: the gate's actual job is "no accidental or undeclared dependency
/// addition to the solution, full stop" — of which forbidding a provider SDK, a validation
/// library, or a mediator (ADR-021) in <c>src/</c> is the headline case, but not the only one a
/// legitimate addition might trip. A future test-only package addition needs a pin update too,
/// following the same update path described above.
/// </para>
/// </remarks>
public sealed class DependencyPinGates
{
    // The pin itself: every package name expected in Directory.Packages.props today. Seeded from
    // the file's actual contents at the time this gate was written — not a rounded or
    // approximate count. Update this array in the same PR as any legitimate
    // Directory.Packages.props change; see the remarks above for the full update path.
    private static readonly string[] PinnedPackageNames =
    {
        "Microsoft.AspNetCore.OpenApi",
        "Microsoft.OpenApi",
        "Microsoft.Identity.Web",
        "Microsoft.AspNetCore.Authentication.JwtBearer",
        "Microsoft.EntityFrameworkCore",
        "Microsoft.EntityFrameworkCore.SqlServer",
        "Microsoft.EntityFrameworkCore.Design",
        "Microsoft.Extensions.Logging.Abstractions",
        "Microsoft.AspNetCore.Mvc.Testing",
        "xunit.v3",
        "Testcontainers.MsSql",
        "SSH.NET",
        "Respawn",
        "AwesomeAssertions",
        "AwesomeAssertions.Analyzers",
        "System.Security.Cryptography.Pkcs",
        "System.Security.Cryptography.Xml",
        "Microsoft.Extensions.Diagnostics.HealthChecks",
        "AspNetCore.HealthChecks.SqlServer",
        "OpenTelemetry",
        "OpenTelemetry.Exporter.OpenTelemetryProtocol",
        "OpenTelemetry.Extensions.Hosting",
        "OpenTelemetry.Instrumentation.AspNetCore",
        "OpenTelemetry.Instrumentation.SqlClient",
    };

    // Naming patterns that would identify a known AI-provider SDK if one were ever pinned. This
    // is deliberately a small, illustrative set (not an exhaustive deny-list): the gate below
    // that uses this only needs to prove today's pin contains none of them, as an explicit,
    // independently-identifiable fact rather than leaving a reader to infer "no provider SDK
    // referenced" from the general pin above.
    private static readonly string[] KnownProviderSdkNamePatterns =
    {
        "OpenAI",
        "Anthropic",
        "Azure.AI.",
        "Azure.OpenAI",
    };

    // Directory names that would indicate an AI Platform capability exists under src/. Mirrors
    // CapabilityBoundaryGates.NoCapabilityOtherThanTenancyExistsUnderSrc and
    // BackgroundJobGates.NoBackgroundJobTypeExistsUnderSrc: a documented snapshot of "does not
    // exist yet," not an enforced naming rule.
    private static readonly string[] AiPlatformCapabilityDirectoryNamePatterns =
    {
        "AIPlatform",
        "AiPlatform",
    };

    [Fact]
    public void CentralPackageSet_MatchesThePinnedNameList()
    {
        var actualNames = ProjectFile.GetCentralPackageVersions()
            .Select(package => package.Name)
            .ToArray();

        actualNames.Should().BeEquivalentTo(
            PinnedPackageNames,
            "Directory.Packages.props' complete package set must match the checked-in pin in " +
            "DependencyPinGates.cs (by name, not version) — this pin is the single control " +
            "point keeping an AI provider SDK, a validation library, or a mediator/dispatcher " +
            "(ADR-021) out of the solution's dependency list undetected. If a package was added " +
            "legitimately, update BOTH Directory.Packages.props AND this file's " +
            "PinnedPackageNames array in the same PR — don't delete this gate.");
    }

    [Fact]
    public void PinnedPackageNames_ContainNoKnownProviderSdkNamePattern()
    {
        // Makes "no provider SDK is referenced" explicit and independently identifiable, rather
        // than relying on a reader to infer it from the general pin test above. This is
        // otherwise already subsumed by CentralPackageSet_MatchesThePinnedNameList: no such
        // package exists in Directory.Packages.props today, so that test would already fail the
        // moment one was added. This test exists so a failure specifically about a provider SDK
        // reads as exactly that, not as an undifferentiated "the general pin changed."
        var matches = PinnedPackageNames
            .Where(name => KnownProviderSdkNamePatterns.Any(pattern =>
                name.Contains(pattern, StringComparison.OrdinalIgnoreCase)))
            .ToArray();

        matches.Should().BeEmpty(
            "no AI provider SDK may be referenced yet — the pinned package list must not " +
            "contain a name matching a known provider-SDK pattern (e.g. OpenAI, Anthropic, " +
            "Azure.AI.*). Matched: " + string.Join(", ", matches));
    }

    [Fact]
    public void NoAiPlatformCapabilityDirectoryExistsUnderSrc()
    {
        // The companion fact to the provider-SDK check above: "no AI Platform capability exists
        // yet." Deliberately a separate [Fact] so that when this eventually fails (expected once
        // a future slice introduces the AI Platform capability), the failure message identifies
        // which of the two independent facts changed — a provider SDK reference, or a capability
        // directory appearing — rather than a single ambiguous combined violation.
        var repoRoot = ProjectFile.GetRepoRoot();
        var srcRoot = Path.Combine(repoRoot, "src");

        var matchingDirectories = Directory
            .GetDirectories(srcRoot)
            .Select(path => Path.GetFileName(path)!)
            .Where(name => AiPlatformCapabilityDirectoryNamePatterns.Any(pattern =>
                name.Contains(pattern, StringComparison.OrdinalIgnoreCase)))
            .ToArray();

        matchingDirectories.Should().BeEmpty(
            "no AI Platform capability may exist under src/ yet — this is a documented " +
            "snapshot, not an enforced naming rule. If this fails because the AI Platform " +
            "capability was legitimately added, that is expected: update this pin, and " +
            "separately confirm the provider-SDK pin above " +
            "(PinnedPackageNames_ContainNoKnownProviderSdkNamePattern) is updated the moment an " +
            "actual provider SDK package is added. Found: " + string.Join(", ", matchingDirectories));
    }
}
