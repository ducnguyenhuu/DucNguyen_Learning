using System.Security.Cryptography;

namespace Identity.Application.Invitations;

/// <summary>
/// Generates, hashes, and verifies invitation bearer tokens (T070), per <c>data-model.md</c>'s
/// <c>Invitation.TokenHash</c> field: "SHA-256 of the token. The token itself is never stored —
/// it is a credential, and a stored credential is a leaked credential (Principle V). Returned
/// once, at creation."
/// </summary>
/// <remarks>
/// <para>
/// A static, stateless helper — no DI, no repository — mirroring <c>RowVersionETag</c>'s shape
/// from Phase 3 (T057). This class only ever deals with the token itself; persisting the
/// resulting hash on an <c>Invitation</c> entity, and the accept-flow lookup, are later tasks
/// (T071+).
/// </para>
/// <para>
/// <b>Encoding:</b> the raw token is 32 cryptographically random bytes (256 bits — matching the
/// 256-bit output of the SHA-256 hash it is stored as), rendered with base64url
/// (<see cref="Base64UrlEncode"/>: standard base64 with <c>+</c>/<c>/</c> swapped for
/// <c>-</c>/<c>_</c> and <c>=</c> padding stripped). <c>contracts/openapi.yaml</c>'s
/// <c>POST /invitations/{token}/accept</c> path parameter is declared only as
/// <c>{ type: string }</c> with no format hint, but it is a URL path segment, so base64url —
/// unlike standard base64 — needs no percent-encoding of its alphabet (no <c>+</c>, <c>/</c>, or
/// <c>=</c>) and round-trips cleanly through routing, query strings, and email links alike.
/// </para>
/// </remarks>
public static class InvitationToken
{
    private const int TokenByteLength = 32;

    /// <summary>
    /// Generates a new cryptographically random invitation token, returned as a base64url string.
    /// </summary>
    /// <remarks>
    /// This is the <b>raw</b> token — the value returned once, at creation, in the API response
    /// / embedded in the invitation email link. It must not be persisted; only
    /// <see cref="Hash"/>'s output is stored (as <c>Invitation.TokenHash</c>).
    /// </remarks>
    /// <returns>A base64url-encoded, 32-byte (256-bit) random token.</returns>
    public static string Generate()
    {
        var bytes = RandomNumberGenerator.GetBytes(TokenByteLength);
        return Base64UrlEncode(bytes);
    }

    /// <summary>
    /// Hashes a raw token to its persisted SHA-256 form.
    /// </summary>
    /// <param name="token">The raw token string, as returned by <see cref="Generate"/>.</param>
    /// <returns>The 32-byte SHA-256 hash, matching <c>data-model.md</c>'s <c>TokenHash: byte[32]</c>.</returns>
    /// <exception cref="ArgumentException"><paramref name="token"/> is null, empty, or whitespace-only.</exception>
    public static byte[] Hash(string token)
    {
        if (string.IsNullOrWhiteSpace(token))
        {
            throw new ArgumentException("Token must not be null or empty.", nameof(token));
        }

        return SHA256.HashData(System.Text.Encoding.UTF8.GetBytes(token));
    }

    /// <summary>
    /// Verifies a presented token against a stored hash, using a constant-time comparison to
    /// avoid timing side-channels on what is effectively a credential comparison.
    /// </summary>
    /// <param name="presentedToken">The raw token presented by the caller (e.g. the path parameter).</param>
    /// <param name="storedHash">The persisted <c>Invitation.TokenHash</c> to compare against.</param>
    /// <returns><see langword="true"/> if <paramref name="presentedToken"/> hashes to <paramref name="storedHash"/>.</returns>
    /// <exception cref="ArgumentException"><paramref name="presentedToken"/> is null, empty, or whitespace-only.</exception>
    /// <exception cref="ArgumentNullException"><paramref name="storedHash"/> is <see langword="null"/>.</exception>
    public static bool Verify(string presentedToken, byte[] storedHash)
    {
        ArgumentNullException.ThrowIfNull(storedHash);

        var presentedHash = Hash(presentedToken);
        return CryptographicOperations.FixedTimeEquals(presentedHash, storedHash);
    }

    private static string Base64UrlEncode(byte[] bytes) =>
        Convert.ToBase64String(bytes)
            .TrimEnd('=')
            .Replace('+', '-')
            .Replace('/', '_');
}
