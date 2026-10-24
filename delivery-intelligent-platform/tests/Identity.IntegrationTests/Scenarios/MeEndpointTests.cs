using System.Net;
using System.Net.Http.Json;
using ArchitectureTests.Support;
using AwesomeAssertions;
using Identity.Domain.Abstractions;
using Identity.IntegrationTests.Infrastructure;
using Xunit;

namespace Identity.IntegrationTests.Scenarios;

/// <summary>
/// <c>GET /me</c> (ADR-025, decision 5): the "what can I do here" call. Any authenticated caller
/// may make it, member or not; it returns the caller's own user id, email and organization role,
/// with <c>role</c> <c>null</c> for a non-member — a normal answer, not an error.
/// </summary>
/// <remarks>
/// It is not behind <c>MembershipResolutionFilter</c>, because a caller who is not a member yet
/// needs it to learn exactly that (and then bootstrap or accept an invitation). It JIT-provisions
/// the caller, so the user id it returns is stable across calls (FR-003).
/// </remarks>
public sealed class MeEndpointTests : IdentityIntegrationTestBase
{
    public MeEndpointTests(SqlServerFixture sqlServerFixture, ApiFactory factory)
        : base(sqlServerFixture, factory)
    {
    }

    /// <summary>
    /// A non-member gets 200 with a <c>null</c> role, not a refusal — even when the organization
    /// already has members.
    /// </summary>
    [Fact]
    public async Task Get_Me_AsNonMember_ReturnsNullRole()
    {
        await Factory.SeedMemberAsync(Role.Administrator);

        using var client = Factory.CreateClientForStranger();

        var response = await client.GetAsync("/me", TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.OK);
        var body = await response.Content.ReadFromJsonAsync<MeResponse>(TestContext.Current.CancellationToken);
        body.Should().NotBeNull();
        body!.UserId.Should().NotBeEmpty();
        body.Role.Should().BeNull();
    }

    /// <summary>
    /// A member gets their own id, email and role — for each role, so a caller can tell an
    /// Administrator from a Member from a Reader without trying an operation.
    /// </summary>
    [Theory]
    [InlineData(Role.Administrator)]
    [InlineData(Role.Member)]
    [InlineData(Role.Reader)]
    public async Task Get_Me_AsMember_ReturnsOwnIdentityAndRole(Role role)
    {
        var member = await Factory.SeedMemberAsync(role);

        using var client = Factory.CreateClientFor(member);

        var response = await client.GetAsync("/me", TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.OK);
        var body = await response.Content.ReadFromJsonAsync<MeResponse>(TestContext.Current.CancellationToken);
        body.Should().Be(new MeResponse(member.UserId.Value, member.Email, role.ToString()));
    }

    /// <summary>
    /// The same identity gets the same user id on every call — the first call provisions the
    /// user, later calls find it (FR-003).
    /// </summary>
    [CoversRequirement("FR-003")]
    [Fact]
    public async Task Get_Me_Repeatedly_ReturnsTheSameUserId()
    {
        using var client = Factory.CreateClientForStranger();

        var first = await client.GetFromJsonAsync<MeResponse>("/me", TestContext.Current.CancellationToken);
        var second = await client.GetFromJsonAsync<MeResponse>("/me", TestContext.Current.CancellationToken);

        first!.UserId.Should().NotBeEmpty();
        second!.UserId.Should().Be(first.UserId);
    }

    /// <summary>
    /// After bootstrapping, the same caller's <c>GET /me</c> reports Administrator.
    /// </summary>
    [Fact]
    public async Task Get_Me_AfterBootstrap_ReturnsAdministrator()
    {
        using var client = Factory.CreateClientForStranger();

        var before = await client.GetFromJsonAsync<MeResponse>("/me", TestContext.Current.CancellationToken);
        var bootstrap = await client.PostAsync("/members/bootstrap", content: null, TestContext.Current.CancellationToken);
        var after = await client.GetFromJsonAsync<MeResponse>("/me", TestContext.Current.CancellationToken);

        before!.Role.Should().BeNull();
        bootstrap.StatusCode.Should().Be(HttpStatusCode.Created);
        after!.Role.Should().Be("Administrator");
        after.UserId.Should().Be(before.UserId);
    }

    /// <summary>No token, no answer: 401 (FR-002).</summary>
    [CoversRequirement("FR-002")]
    [Fact]
    public async Task Get_Me_WithoutAuthentication_IsRejectedAsUnauthenticated()
    {
        using var client = Factory.CreateClient();

        var response = await client.GetAsync("/me", TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.Unauthorized);
    }

    private sealed record MeResponse(Guid UserId, string Email, string? Role);
}
