using System.Net;
using AwesomeAssertions;
using Identity.Domain.Abstractions;
using Identity.IntegrationTests.Infrastructure;
using Xunit;

namespace Identity.IntegrationTests.Observability;

/// <summary>
/// FR-004's span/log enrichment with user identity "when known at the point of emission".
/// <see cref="Identity.Api.Middleware.UserIdentityEnrichmentMiddleware"/>, registered right after
/// <c>app.UseAuthentication()</c>, pushes a <c>UserId</c> log scope (and tags the span with
/// <c>user.id</c>) for every authenticated request, whether or not the route resolves a
/// membership. No tenant attribute exists any more (ADR-025, decision 7), so these tests also
/// prove none is emitted. The unauthenticated edge case — nothing known, nothing attached — must
/// never fail the request for enrichment's sake.
/// </summary>
public sealed class UserEnrichmentTests : IdentityIntegrationTestBase
{
    public UserEnrichmentTests(SqlServerFixture sqlServerFixture, ApiFactory factory)
        : base(sqlServerFixture, factory)
    {
    }

    /// <summary>
    /// A member-only request (<c>GET /members</c>, behind <c>MembershipResolutionFilter</c>)
    /// produces log lines carrying the caller's user id in their active scopes, including the
    /// filter's own "Membership resolved" line.
    /// </summary>
    [Fact]
    public async Task MemberOnlyRequest_LogLine_CarriesUserId_AndNoTenantId()
    {
        var administrator = await Factory.SeedMemberAsync(Role.Administrator);

        Factory.ClearCapturedLogs();

        using var client = Factory.CreateClientFor(administrator);
        var response = await client.GetAsync("/members", TestContext.Current.CancellationToken);
        response.EnsureSuccessStatusCode();
        _ = await response.Content.ReadAsStringAsync(TestContext.Current.CancellationToken);

        var capturedLogs = Factory.CapturedLogMessages;
        var expectedUserId = administrator.EntraObjectId.ToString();

        capturedLogs.Should().Contain(
            message => message.Contains("Membership resolved", StringComparison.Ordinal)
                && message.Contains($"UserId={expectedUserId}", StringComparison.OrdinalIgnoreCase),
            "a member-only request must produce log lines carrying the caller's UserId " +
            $"({expectedUserId}) in their active scopes. Captured log messages were: " +
            $"[{string.Join(" | ", capturedLogs)}].");

        capturedLogs.Should().NotContain(
            // A leading space distinguishes a "TenantId=" scope key from unrelated substrings
            // such as EF Core's "@entraTenantId=" parameter-log text.
            message => message.Contains(" TenantId=", StringComparison.OrdinalIgnoreCase),
            "there is no application tenancy, so no log line may carry a TenantId scope.");
    }

    /// <summary>
    /// A route that does not resolve membership (<c>GET /me</c>, callable by non-members) still
    /// gets user-identity enrichment: the user id is known as soon as authentication runs.
    /// </summary>
    [Fact]
    public async Task NonMemberRoute_SucceedsAndCarriesUserId()
    {
        Factory.ClearCapturedLogs();

        var entraObjectId = Guid.NewGuid();
        using var client = Factory.CreateClientFor(Guid.NewGuid(), entraObjectId);
        var response = await client.GetAsync("/me", TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.OK);
        _ = await response.Content.ReadAsStringAsync(TestContext.Current.CancellationToken);

        var capturedLogs = Factory.CapturedLogMessages;

        capturedLogs.Should().Contain(
            message => message.Contains($"UserId={entraObjectId}", StringComparison.OrdinalIgnoreCase),
            "user-identity enrichment applies to every authenticated request, independent of " +
            $"membership. Captured log messages were: [{string.Join(" | ", capturedLogs)}].");
    }

    /// <summary>
    /// An unauthenticated request must not fail because identity enrichment has nothing to
    /// attach — enrichment happens with whatever context exists (none, here) and never blocks
    /// the request.
    /// </summary>
    [Fact]
    public async Task Unauthenticated_DoesNotFailForEnrichmentReasons()
    {
        using var client = Factory.CreateClient();

        // No Authorization header at all: TestAuthHandler returns NoResult(), so the request
        // reaches UserIdentityEnrichmentMiddleware with no authenticated User — it must skip
        // enrichment, not throw.
        var response = await client.GetAsync("/me", TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(
            HttpStatusCode.Unauthorized,
            "an unauthenticated request is rejected by UseAuthorization() — and for that reason " +
            "alone, not because identity enrichment malfunctioned with no identity present.");
    }
}
