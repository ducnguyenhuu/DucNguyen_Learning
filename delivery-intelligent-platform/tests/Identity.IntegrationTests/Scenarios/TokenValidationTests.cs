using System.Net;
using System.Net.Http.Headers;
using ArchitectureTests.Support;
using Identity.IntegrationTests.Infrastructure;
using AwesomeAssertions;
using Xunit;

namespace Identity.IntegrationTests.Scenarios;

/// <summary>
/// <b>401 Unauthorized</b> for four distinct ways a real, signed JWT can fail validation under the
/// genuine <c>JwtBearer</c> scheme (the production auth configuration) — expired, wrong audience,
/// wrong issuer, and invalid signature (FR-001, FR-004).
/// </summary>
/// <remarks>
/// Unlike <see cref="UnauthenticatedTests"/> (no <c>Authorization</c> header at all), every
/// request here sends <c>Authorization: Bearer {jwt}</c>, which <c>ApiFactory</c>'s
/// <c>PolicyScheme.ForwardDefaultSelector</c> forwards to the <em>real</em>
/// <c>JwtBearerHandler</c> — so these exercise genuine cryptographic and claims validation in the
/// production <c>TokenValidationParameters</c> pipeline: lifetime, audience pinning, issuer
/// pinning and RSA signature verification. The probe route is <c>GET /me</c>, which any validly
/// authenticated caller may call, so a 401 can only come from token validation.
/// </remarks>
public sealed class TokenValidationTests : IdentityIntegrationTestBase, IDisposable
{

    // Constructed directly (not injected as a fixture) per SignedTokenHarness's contract — but deliberately
    // *not* used to mint the tokens below. ApiFactory already owns its own
    // SignedTokenHarness instance (exposed via ApiFactory.TokenHarness) and configures the real
    // JwtBearer scheme to trust only that instance's PublicSigningKey. Minting from a second,
    // independent harness here would sign every token — including the ones meant to be
    // otherwise-valid — with a key the host never trusts, breaking the "wrong audience"/"wrong
    // issuer"/"expired" cases (which need everything else about the token to be valid) and
    // making the "invalid signature" case indistinguishable from them. This field exists solely
    // to demonstrate SignedTokenHarness's IDisposable contract is honored even when a test class also has
    // access to a shared, factory-owned harness.
    private readonly SignedTokenHarness _tokenHarness = new();

    public TokenValidationTests(SqlServerFixture sqlServerFixture, ApiFactory factory)
        : base(sqlServerFixture, factory)
    {
    }

    [CoversRequirement("FR-001")]
    [CoversRequirement("FR-004")]
    [Fact]
    public async Task Get_Me_WithExpiredToken_ReturnsUnauthorized()
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
            "/me",
            TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.Unauthorized);
    }

    [CoversRequirement("FR-001")]
    [CoversRequirement("FR-004")]
    [Fact]
    public async Task Get_Me_WithWrongAudience_ReturnsUnauthorized()
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
            "/me",
            TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.Unauthorized);
    }

    [CoversRequirement("FR-001")]
    [CoversRequirement("FR-004")]
    [Fact]
    public async Task Get_Me_WithWrongIssuer_ReturnsUnauthorized()
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
            "/me",
            TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.Unauthorized);
    }

    [CoversRequirement("FR-001")]
    [CoversRequirement("FR-004")]
    [Fact]
    public async Task Get_Me_WithInvalidSignature_ReturnsUnauthorized()
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
            "/me",
            TestContext.Current.CancellationToken);

        response.StatusCode.Should().Be(HttpStatusCode.Unauthorized);
    }

    public void Dispose()
    {
        _tokenHarness.Dispose();
    }
}
