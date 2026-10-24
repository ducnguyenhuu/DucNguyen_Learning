using System.Security.Cryptography;
using Microsoft.IdentityModel.JsonWebTokens;
using Microsoft.IdentityModel.Tokens;

namespace Identity.IntegrationTests.Infrastructure;

/// <summary>
/// Tier 2 test harness: mints real, signed JWTs and exposes the RSA keys
/// needed to make the real <c>Microsoft.Identity.Web</c> / JwtBearer
/// validation pipeline (T032) actually validate them, with no dependency on
/// a live Entra endpoint.
/// </summary>
/// <remarks>
/// Tier 1 (<see cref="TestAuthHandler"/>) proves "does my endpoint behave
/// correctly given a claims principal." It can never prove "does my JWT
/// bearer configuration actually validate tokens correctly" — a fake handler
/// is structurally blind to a misconfigured audience, issuer, or a
/// <c>MapInboundClaims</c> mismatch. This harness closes that gap by
/// generating a test-only RSA key pair and minting tokens signed with the
/// private half, so <c>ApiFactory</c> (T042) can configure the real
/// <c>JwtBearerOptions.TokenValidationParameters.IssuerSigningKey</c> with the
/// public half and run tokens through the genuine validation pipeline.
///
/// The RSA key pair is generated fresh per instance (per test run) and never
/// persisted — it only ever needs to sign and verify within this one
/// process, so there is nothing to rotate or protect beyond the process
/// lifetime.
///
/// For the "invalid signature" negative case (T047), callers can either mint
/// with the primary key and a wrong claim (audience/issuer/expiry — already
/// covered by <see cref="MintToken"/>'s parameters), or use
/// <see cref="WrongSigningCredentials"/>, a second, throwaway RSA key this
/// harness never registers as trusted with <see cref="PublicSigningKey"/>.
/// Signing with that key produces a token whose signature is genuine JWT
/// syntax but fails validation against the key <c>ApiFactory</c> configures
/// as trusted — exactly the "invalid signature" shape T047 needs, without
/// having to hand-corrupt token bytes.
/// </remarks>
public sealed class SignedTokenHarness : IDisposable
{
    private readonly RSA _signingKey;
    private readonly RSA _wrongKey;
    private readonly JsonWebTokenHandler _handler = new();

    public SignedTokenHarness()
    {
        _signingKey = RSA.Create(2048);
        _wrongKey = RSA.Create(2048);
    }

    /// <summary>
    /// The public half of this harness's primary signing key. <c>ApiFactory</c>
    /// (T042) overrides <c>TokenValidationParameters.IssuerSigningKey</c> with
    /// this so the real validation pipeline trusts tokens minted by
    /// <see cref="MintToken"/> without fetching OIDC metadata from a live
    /// Entra endpoint (which would fail or hang without network access, and
    /// would defeat the point of this tier — testing validation logic against
    /// a controlled key, not live Entra connectivity).
    /// </summary>
    public RsaSecurityKey PublicSigningKey =>
        new(_signingKey.ExportParameters(includePrivateParameters: false));

    /// <summary>
    /// Signing credentials built from a second RSA key this harness never
    /// exposes via <see cref="PublicSigningKey"/>. Use these to mint a
    /// token for the "invalid signature" negative test (T047): the token is
    /// well-formed but signed with a key <c>ApiFactory</c> never configured
    /// as trusted, so validation must fail on the signature check.
    /// </summary>
    public SigningCredentials WrongSigningCredentials =>
        new(new RsaSecurityKey(_wrongKey), SecurityAlgorithms.RsaSha256);

    /// <summary>
    /// Mints a signed JWT with literal <c>"tid"</c>/<c>"oid"</c> claim types
    /// (matching T032/T040's <c>MapInboundClaims = false</c> decision — the
    /// production pipeline and this harness must agree on claim names, or a
    /// bug that passes tests here would still 403 in production).
    /// </summary>
    /// <param name="tid">Tenant id, emitted as claim <c>"tid"</c>.</param>
    /// <param name="oid">Object (user) id, emitted as claim <c>"oid"</c>.</param>
    /// <param name="audience">Token audience.</param>
    /// <param name="issuer">Token issuer.</param>
    /// <param name="notBefore">
    /// Optional not-before instant; defaults to now, allowing an already-expired
    /// window to be constructed by pairing a past <paramref name="notBefore"/>
    /// with a past <paramref name="expires"/>.
    /// </param>
    /// <param name="expires">Optional expiry instant; defaults to one hour from now.</param>
    /// <param name="signingCredentials">
    /// Optional override signing credentials. Defaults to this harness's
    /// primary key (<see cref="PublicSigningKey"/>'s private half). Pass
    /// <see cref="WrongSigningCredentials"/> to mint an invalid-signature
    /// token for negative tests.
    /// </param>
    public string MintToken(
        Guid tid,
        Guid oid,
        string audience,
        string issuer,
        DateTime? notBefore = null,
        DateTime? expires = null,
        SigningCredentials? signingCredentials = null)
    {
        var now = DateTime.UtcNow;

        var descriptor = new SecurityTokenDescriptor
        {
            Audience = audience,
            Issuer = issuer,
            NotBefore = notBefore ?? now,
            Expires = expires ?? now.AddHours(1),
            SigningCredentials = signingCredentials
                ?? new SigningCredentials(new RsaSecurityKey(_signingKey), SecurityAlgorithms.RsaSha256),
            Claims = new Dictionary<string, object>
            {
                ["tid"] = tid.ToString(),
                ["oid"] = oid.ToString(),

                // Microsoft.Identity.Web's AddMicrosoftIdentityWebApi wires an OnTokenValidated
                // handler (IDW10201) that runs *after* the standard JwtBearer validation
                // (signature/audience/issuer/lifetime) succeeds, and unconditionally rejects any
                // otherwise-valid token that carries neither a "scp" (delegated) nor "roles"
                // (app-only) claim — a real Entra-issued access token always carries one of the
                // two. Without this, every token this harness mints fails validation for a reason
                // that has nothing to do with signature/audience/issuer/lifetime, which T047's
                // negative tests never notice (they're already rejected earlier, before
                // OnTokenValidated runs) but a positive/neutral test like RevocationWindowTests'
                // Half 2 does.
                ["scp"] = "access_as_user",
            },
        };

        return _handler.CreateToken(descriptor);
    }

    public void Dispose()
    {
        _signingKey.Dispose();
        _wrongKey.Dispose();
    }
}
