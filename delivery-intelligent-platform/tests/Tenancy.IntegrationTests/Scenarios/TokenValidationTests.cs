using System.Net;
using System.Net.Http.Headers;
using ArchitectureTests.Support;
using Tenancy.IntegrationTests.Infrastructure;
using AwesomeAssertions;
using Xunit;

namespace Tenancy.IntegrationTests.Scenarios;

/// <summary>
/// Failing test (T047) asserting <b>401 Unauthorized</b> for four distinct ways a real, signed
/// JWT can fail validation under the genuine <c>JwtBearer</c> scheme (T032's production auth
/// configuration) — expired, wrong audience, wrong issuer, and invalid signature (FR-004).
/// </summary>
/// <remarks>
/// <b>Why this file is different from the other 401/404 tests in this block.</b>
/// <see cref="UnauthenticatedTests"/> and its siblings assert 401 for requests that never
/// present an <c>Authorization</c> header at all (or present T040's Tier 1 fake-scheme header),
/// and today they genuinely fail with a 404 because <c>/tenants</c> routes don't exist yet
/// (T058 adds them) — a "route absent" failure, which is a known, uninteresting signal.
/// <para>
/// This file is different: every request here sends <c>Authorization: Bearer {jwt}</c>, which
/// (per <c>ApiFactory</c>'s <c>PolicyScheme.ForwardDefaultSelector</c>) forwards to the *real*
/// <c>JwtBearerHandler</c> — not the Tier 1 fake. Right now it will still likely show 404
/// because there's no route to hit 401 against in the first place, so its failure mode today is
/// the same uninteresting "route absent" 404. But unlike the other tests, once T058 lands real
/// endpoints, these four tests will exercise **genuine cryptographic/claims validation** in the
/// production <c>TokenValidationParameters</c> pipeline — expired-lifetime rejection, audience
/// pinning, issuer pinning, and RSA signature verification — not a routing artifact. Their value
/// is in what they become, not what they show today.
/// </para>
/// </remarks>
public sealed class TokenValidationTests : TenancyIntegrationTestBase, IDisposable
{

    // Constructed directly (not injected as a fixture) per T041's contract — but deliberately
    // *not* used to mint the tokens below. ApiFactory (T042) already owns its own
    // SignedTokenHarness instance (exposed via ApiFactory.TokenHarness) and configures the real
    // JwtBearer scheme to trust only that instance's PublicSigningKey. Minting from a second,
    // independent harness here would sign every token — including the ones meant to be
    // otherwise-valid — with a key the host never trusts, breaking the "wrong audience"/"wrong
    // issuer"/"expired" cases (which need everything else about the token to be valid) and
    // making the "invalid signature" case indistinguishable from them. This field exists solely
    // to demonstrate T041's IDisposable contract is honored even when a test class also has
    // access to a shared, factory-owned harness.
    private readonly SignedTokenHarness _tokenHarness = new();

    public TokenValidationTests(SqlServerFixture sqlServerFixture, ApiFactory factory)
        : base(sqlServerFixture, factory)
    {
    }

    [CoversRequirement("FR-001")]
    [CoversRequirement("FR-004")]
    [Fact]
    public async Task Get_TenantById_WithExpiredToken_ReturnsUnauthorized()
    {
        await Factory.InitializeDatabaseAsync();

        using var client = Factory.CreateClient();

        // Invalid because: NotBefore/Expires are both in the past, so ValidateLifetime rejects
        // the token on expiry alone even though issuer/audience/signature are all otherwise
        // valid and trusted.
        var token = Factory.TokenHarness.MintToken(
            tid: Guid.NewGuid(),
            oid: Guid.NewGuid(),
            audience: ApiFactory.ExpectedAudience,
            issuer: ApiFactory.ExpectedIssuer,
            notBefore: DateTime.UtcNow.AddMinutes(-10),
            expires: DateTime.UtcNow.AddMinutes(-5));

        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", token);

        var response = await client.GetAsync(
            $"/tenants/{Guid.NewGuid()}",
            TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.Unauthorized);
    }

    [CoversRequirement("FR-001")]
    [CoversRequirement("FR-004")]
    [Fact]
    public async Task Get_TenantById_WithWrongAudience_ReturnsUnauthorized()
    {
        await Factory.InitializeDatabaseAsync();

        using var client = Factory.CreateClient();

        // Invalid because: the audience claim does not match ApiFactory.ExpectedAudience, so
        // ValidateAudience rejects the token even though issuer, signature, and expiry are all
        // otherwise valid and trusted.
        var token = Factory.TokenHarness.MintToken(
            tid: Guid.NewGuid(),
            oid: Guid.NewGuid(),
            audience: "api://some-other-app",
            issuer: ApiFactory.ExpectedIssuer);

        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", token);

        var response = await client.GetAsync(
            $"/tenants/{Guid.NewGuid()}",
            TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.Unauthorized);
    }

    [CoversRequirement("FR-001")]
    [CoversRequirement("FR-004")]
    [Fact]
    public async Task Get_TenantById_WithWrongIssuer_ReturnsUnauthorized()
    {
        await Factory.InitializeDatabaseAsync();

        using var client = Factory.CreateClient();

        // Invalid because: the issuer claim does not match ApiFactory.ExpectedIssuer, so
        // ValidateIssuer rejects the token even though audience, signature, and expiry are all
        // otherwise valid and trusted.
        var token = Factory.TokenHarness.MintToken(
            tid: Guid.NewGuid(),
            oid: Guid.NewGuid(),
            audience: ApiFactory.ExpectedAudience,
            issuer: "https://login.microsoftonline.com/some-other-tenant/v2.0");

        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", token);

        var response = await client.GetAsync(
            $"/tenants/{Guid.NewGuid()}",
            TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.Unauthorized);
    }

    [CoversRequirement("FR-001")]
    [CoversRequirement("FR-004")]
    [Fact]
    public async Task Get_TenantById_WithInvalidSignature_ReturnsUnauthorized()
    {
        await Factory.InitializeDatabaseAsync();

        using var client = Factory.CreateClient();

        // Invalid because: the token is signed with SignedTokenHarness.WrongSigningCredentials —
        // a second RSA key ApiFactory never configured as trusted via PublicSigningKey — so
        // signature verification fails even though issuer, audience, and expiry claims are all
        // otherwise valid.
        var token = Factory.TokenHarness.MintToken(
            tid: Guid.NewGuid(),
            oid: Guid.NewGuid(),
            audience: ApiFactory.ExpectedAudience,
            issuer: ApiFactory.ExpectedIssuer,
            signingCredentials: Factory.TokenHarness.WrongSigningCredentials);

        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", token);

        var response = await client.GetAsync(
            $"/tenants/{Guid.NewGuid()}",
            TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.Unauthorized);
    }

    public void Dispose()
    {
        _tokenHarness.Dispose();
    }
}
