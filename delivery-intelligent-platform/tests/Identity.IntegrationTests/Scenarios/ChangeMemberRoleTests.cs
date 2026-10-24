using System.Net;
using System.Net.Http.Json;
using ArchitectureTests.Support;
using AwesomeAssertions;
using Identity.Api.ETags;
using Identity.Domain.Abstractions;
using Identity.Domain.Memberships;
using Identity.IntegrationTests.Infrastructure;
using Xunit;

namespace Identity.IntegrationTests.Scenarios;

/// <summary>
/// <c>PATCH /members/{userId}</c> — changing an active member's role, including refusal when the
/// change would demote the organization's sole remaining <see cref="Role.Administrator"/>
/// (<see cref="OrganizationAdministration"/>'s last-administrator invariant, FR-015, exercised
/// end-to-end), and the 428/400/412 <c>If-Match</c> handling the route shares with
/// <c>DELETE /members/{userId}</c>.
/// </summary>
public sealed class ChangeMemberRoleTests : IdentityIntegrationTestBase
{

    public ChangeMemberRoleTests(SqlServerFixture sqlServerFixture, ApiFactory factory)
        : base(sqlServerFixture, factory)
    {
    }

    /// <summary>
    /// Happy path: an administrator changes another member's role from <see cref="Role.Member"/>
    /// to <see cref="Role.Reader"/> — per Assumption 5, Member and Reader are behaviorally
    /// identical, so this is purely a mechanism check, not a proof of behavioral difference.
    /// Asserts <c>200</c>, the new role in the response body, and a fresh <c>ETag</c> distinct
    /// from the <c>If-Match</c> presented on the request.
    /// </summary>
    [CoversRequirement("FR-014")]
    [Fact]
    public async Task Patch_MemberRole_AsAdministrator_ChangesRoleAndReturnsFreshETag()
    {
        var seed = await SeedAdministratorAndMemberAsync();

        using var adminClient = CreateAuthenticatedClient(seed.Administrator);
        var ifMatch = await Factory.GetMembershipIfMatchAsync(seed.Member.MembershipId);
        adminClient.DefaultRequestHeaders.Add("If-Match", ifMatch);

        var response = await adminClient.PatchAsJsonAsync(
            $"/members/{seed.Member.UserId.Value}",
            new { role = "Reader" },
            TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.OK);

        var body = await response.Content.ReadAsStringAsync(TestContext.Current.CancellationToken);
        body.Should().Contain("Reader");

        response.Headers.ETag.Should().NotBeNull();
        response.Headers.ETag!.ToString().Should().NotBe(ifMatch);
    }

    /// <summary>
    /// Last-administrator demotion refusal: the organization's sole administrator attempts to change
    /// their own role away from <see cref="Role.Administrator"/>. Per 
    /// <see cref="OrganizationAdministration.EnsureRoleChangeAllowed"/>, this must be refused with
    /// <c>409 Conflict</c> rather than leaving the organization with zero active administrators.
    /// </summary>
    [CoversRequirement("FR-015")]
    [Fact]
    public async Task Patch_MemberRole_SoleAdministratorDemotesSelf_IsRefused()
    {
        var seed = await Factory.SeedMemberAsync(Role.Administrator);

        using var client = Factory.CreateClientFor(seed);

        var ifMatch = await Factory.GetMembershipIfMatchAsync(seed.MembershipId);
        client.DefaultRequestHeaders.Add("If-Match", ifMatch);

        var response = await client.PatchAsJsonAsync(
            $"/members/{seed.UserId.Value}",
            new { role = "Member" },
            TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.Conflict);
    }

    /// <summary>
    /// <c>If-Match</c> handling, test 1: a request with no <c>If-Match</c> header at all is
    /// rejected with <c>428 Precondition Required</c>, mirroring <c>DELETE /members/{userId}</c>.
    /// </summary>
    [CoversRequirement("FR-014")]
    [CoversRequirement("FR-021")]
    [Fact]
    public async Task Patch_MemberRole_WithoutIfMatchHeader_ReturnsPreconditionRequired()
    {
        var seed = await SeedAdministratorAndMemberAsync();

        using var adminClient = CreateAuthenticatedClient(seed.Administrator);

        var response = await adminClient.PatchAsJsonAsync(
            $"/members/{seed.Member.UserId.Value}",
            new { role = "Reader" },
            TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be((HttpStatusCode)428);
    }

    /// <summary>
    /// <c>If-Match</c> handling, test 2: a malformed <c>If-Match</c> value (not a well-formed
    /// quoted base64 ETag — <see cref="RowVersionETag.FromIfMatch"/> throws
    /// <see cref="FormatException"/>) is rejected with <c>400 Bad Request</c>.
    /// </summary>
    [CoversRequirement("FR-014")]
    [CoversRequirement("FR-021")]
    [Fact]
    public async Task Patch_MemberRole_WithMalformedIfMatchHeader_ReturnsBadRequest()
    {
        var seed = await SeedAdministratorAndMemberAsync();

        using var adminClient = CreateAuthenticatedClient(seed.Administrator);

        using var request = new HttpRequestMessage(
            HttpMethod.Patch,
            $"/members/{seed.Member.UserId.Value}")
        {
            Content = JsonContent.Create(new { role = "Reader" }),
        };
        request.Headers.TryAddWithoutValidation("If-Match", "not-a-valid-etag");

        var response = await adminClient.SendAsync(request, TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.BadRequest);
    }

    /// <summary>
    /// <c>If-Match</c> handling, test 3: a well-formed but stale <c>If-Match</c> (doesn't match
    /// the membership's current <c>rowversion</c>) is rejected with <c>412 Precondition Failed</c>
    /// — the caller's view of the resource was out of date at request time.
    /// </summary>
    [CoversRequirement("FR-014")]
    [CoversRequirement("FR-021")]
    [Fact]
    public async Task Patch_MemberRole_WithStaleIfMatchHeader_ReturnsPreconditionFailed()
    {
        var seed = await SeedAdministratorAndMemberAsync();

        using var adminClient = CreateAuthenticatedClient(seed.Administrator);
        var staleIfMatch = RowVersionETag.ToETag([0, 0, 0, 0, 0, 0, 0, 1]);
        adminClient.DefaultRequestHeaders.Add("If-Match", staleIfMatch);

        var response = await adminClient.PatchAsJsonAsync(
            $"/members/{seed.Member.UserId.Value}",
            new { role = "Reader" },
            TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be((HttpStatusCode)412);
    }

    /// <summary>
    /// Not-found: the target <c>userId</c> has no active membership — a genuinely unknown user id,
    /// never seeded as a member at all — so the request is
    /// rejected with <c>404 Not Found</c>.
    /// </summary>
    [CoversRequirement("FR-014")]
    [Fact]
    public async Task Patch_MemberRole_ForUserWithNoActiveMembership_ReturnsNotFound()
    {
        var seed = await SeedAdministratorAndMemberAsync();

        using var adminClient = CreateAuthenticatedClient(seed.Administrator);
        var unknownUserId = UserId.New();

        var response = await adminClient.PatchAsJsonAsync(
            $"/members/{unknownUserId.Value}",
            new { role = "Reader" },
            TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.NotFound);
    }

    private HttpClient CreateAuthenticatedClient(SeededMember member) => Factory.CreateClientFor(member);

    /// <summary>
    /// One Administrator (the caller) and a separate Member (the target being role-changed).
    /// </summary>
    private async Task<AdministratorAndMemberSeed> SeedAdministratorAndMemberAsync() =>
        new(await Factory.SeedMemberAsync(Role.Administrator), await Factory.SeedMemberAsync(Role.Member));

    private sealed record AdministratorAndMemberSeed(SeededMember Administrator, SeededMember Member);
}
