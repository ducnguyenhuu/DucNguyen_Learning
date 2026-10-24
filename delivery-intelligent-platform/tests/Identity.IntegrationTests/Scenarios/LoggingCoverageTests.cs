using System.Net;
using System.Net.Http.Json;
using ArchitectureTests.Support;
using AwesomeAssertions;
using Identity.Domain.Abstractions;
using Identity.IntegrationTests.Infrastructure;
using Xunit;

namespace Identity.IntegrationTests.Scenarios;

/// <summary>
/// FR-025 coverage: proves the <em>substantive</em> half of FR-025 — that a membership change, a
/// membership-resolution refusal and a role refusal actually produce a structured, diagnosable
/// log entry — which <see cref="LogHygieneTests"/> explicitly disclaims covering (it only proves
/// incidental framework logging never leaks a secret or token).
/// </summary>
/// <remarks>
/// Uses the same <see cref="ApiFactory.CapturedLogMessages"/> / <see cref="ApiFactory.ClearCapturedLogs"/>
/// capture mechanism as <see cref="LogHygieneTests"/>. Every assertion also checks the entry
/// carries ids only, never an email address — the unnecessary personal data FR-025 forbids.
/// </remarks>
public sealed class LoggingCoverageTests : IdentityIntegrationTestBase
{
    public LoggingCoverageTests(SqlServerFixture sqlServerFixture, ApiFactory factory)
        : base(sqlServerFixture, factory)
    {
    }

    /// <summary>
    /// FR-025's "membership change" category, first case: bootstrapping the first administrator
    /// logs the new administrator's user id (<c>BootstrapAdministrator</c>'s
    /// <c>"User {UserId} bootstrapped as the first administrator"</c>) and not their email.
    /// </summary>
    [CoversRequirement("FR-025")]
    [Fact]
    public async Task Post_Bootstrap_LogsBootstrapWithUserId_AndNoEmail()
    {
        const string email = "first-admin@logging-coverage.example.com";
        using var client = Factory.CreateClientForStranger();
        client.DefaultRequestHeaders.Add("X-Test-Email", email);

        Factory.ClearCapturedLogs();

        var response = await client.PostAsync("/members/bootstrap", content: null, TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.Created);
        var body = await response.Content.ReadFromJsonAsync<MemberResponse>(TestContext.Current.CancellationToken);

        var capturedLogs = Factory.CapturedLogMessages;

        capturedLogs.Should().Contain(
            message => message.Contains("bootstrapped as the first administrator", StringComparison.Ordinal)
                && message.Contains(body!.UserId.ToString(), StringComparison.OrdinalIgnoreCase),
            "FR-025 requires the bootstrap to be logged with enough structured detail to diagnose " +
            "it — at minimum the new administrator's user id.");

        capturedLogs.Should().NotContain(
            message => message.Contains(email, StringComparison.OrdinalIgnoreCase),
            "FR-025 forbids logging unnecessary personal data — the email is not needed to " +
            "diagnose a bootstrap.");
    }

    /// <summary>
    /// FR-025's "authorisation refusal" category, at the membership-resolution layer: an
    /// authenticated caller with no membership is refused, and <c>MembershipResolutionFilter</c>
    /// logs why (<c>"Membership resolution failed: {Reason}"</c>) server-side, while the 403
    /// response itself says nothing beyond "forbidden".
    /// </summary>
    [CoversRequirement("FR-025")]
    [Fact]
    public async Task Get_Members_AsNonMember_LogsMembershipResolutionFailure()
    {
        await Factory.SeedMemberAsync(Role.Administrator);
        using var client = Factory.CreateClientForStranger();

        Factory.ClearCapturedLogs();

        var response = await client.GetAsync("/members", TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.Forbidden);

        Factory.CapturedLogMessages.Should().Contain(
            message => message.Contains("Membership resolution failed", StringComparison.Ordinal),
            "FR-025 requires authorisation refusals to be logged server-side with enough detail " +
            "to diagnose them.");
    }

    /// <summary>
    /// FR-025's "membership change" category: removing an active member must produce a
    /// structured log entry (see <c>RemoveMember.ExecuteAsync</c>'s logging call), scoped by
    /// user/membership id only — no email address, which is exactly the kind of unnecessary
    /// personal data FR-025 forbids.
    /// </summary>
    [CoversRequirement("FR-025")]
    [Fact]
    public async Task Delete_Member_LogsMembershipChange_ByUserIdOnly_NoEmail()
    {
        var seed = await SeedAdministratorAndMemberAsync();

        using var adminClient = Factory.CreateClientFor(seed.Administrator);

        var ifMatch = await Factory.GetMembershipIfMatchAsync(seed.Member.MembershipId);
        adminClient.DefaultRequestHeaders.Add("If-Match", ifMatch);

        Factory.ClearCapturedLogs();

        var deleteResponse = await adminClient.DeleteAsync(
            $"/members/{seed.Member.UserId.Value}",
            TestContext.Current.CancellationToken);

        deleteResponse.StatusCode.Should().Be(HttpStatusCode.NoContent);

        var capturedLogs = Factory.CapturedLogMessages;

        capturedLogs.Should().Contain(
            message => message.Contains(seed.Member.UserId.Value.ToString(), StringComparison.OrdinalIgnoreCase),
            "FR-025 requires membership changes (here, removal) to be logged with enough " +
            "structured detail to diagnose them — at minimum the removed member's user id.");

        capturedLogs.Should().NotContain(
            message => message.Contains("member@logging-coverage.example.com", StringComparison.OrdinalIgnoreCase),
            "FR-025 forbids logging unnecessary personal data — the removed member's email " +
            "address is not required to diagnose a removal event and must not appear in any " +
            "log line.");
    }

    /// <summary>
    /// FR-025's "authorisation refusal" category, at the role-check layer: a caller who <em>is</em>
    /// a member but lacks the Administrator role must produce a structured log entry documenting
    /// the refusal (see <see cref="Identity.Api.Authorization.AdministratorOnlyAuthorizationHandler"/>'s
    /// <c>"Authorization refused: user {UserId}, required role {RequiredRole}, actual role
    /// {ActualRole}"</c>). Distinct from <see cref="Get_Members_AsNonMember_LogsMembershipResolutionFailure"/>,
    /// which covers the earlier "not a member at all" refusal — this one is refused by
    /// <c>RequireAdministratorFilter</c>, not by <c>MembershipResolutionFilter</c>.
    /// </summary>
    [CoversRequirement("FR-025")]
    [Fact]
    public async Task Delete_Member_AsNonAdministrator_LogsAuthorizationRefusal()
    {
        var seed = await SeedAdministratorAndMemberAsync();

        using var memberClient = Factory.CreateClientFor(seed.Member);

        Factory.ClearCapturedLogs();

        var deleteResponse = await memberClient.DeleteAsync(
            $"/members/{seed.Administrator.UserId.Value}",
            TestContext.Current.CancellationToken);

        deleteResponse.StatusCode.Should().Be(HttpStatusCode.Forbidden);

        var capturedLogs = Factory.CapturedLogMessages;

        capturedLogs.Should().Contain(
            message => message.Contains("Authorization refused", StringComparison.Ordinal)
                && message.Contains(seed.Member.UserId.Value.ToString(), StringComparison.OrdinalIgnoreCase)
                && message.Contains("Member", StringComparison.Ordinal),
            "FR-025 requires role-based authorization refusals to be logged server-side with " +
            "enough structured detail (user, required role, actual role) to diagnose them.");

        capturedLogs.Should().NotContain(
            message => message.Contains("member@logging-coverage.example.com", StringComparison.OrdinalIgnoreCase)
                || message.Contains("admin@logging-coverage.example.com", StringComparison.OrdinalIgnoreCase),
            "FR-025 forbids logging unnecessary personal data — no email address must appear in " +
            "the authorization-refusal log line.");
    }

    private async Task<AdministratorAndMemberSeed> SeedAdministratorAndMemberAsync() =>
        new(
            await Factory.SeedMemberAsync(Role.Administrator, "admin@logging-coverage.example.com"),
            await Factory.SeedMemberAsync(Role.Member, "member@logging-coverage.example.com"));

    private sealed record AdministratorAndMemberSeed(SeededMember Administrator, SeededMember Member);

    private sealed record MemberResponse(Guid UserId, string Email, string Role, string Status);
}
