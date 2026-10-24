using System.Diagnostics.CodeAnalysis;

namespace Identity.Api.ETags;

/// <summary>
/// Encodes/decodes SQL Server <c>rowversion</c> bytes (see <c>Tenant.RowVersion</c>, T025 —
/// EF <c>.IsRowVersion()</c>) as HTTP <c>ETag</c>/<c>If-Match</c> header values (T057).
/// </summary>
/// <remarks>
/// <para>
/// Per <c>contracts/openapi.yaml</c>'s <c>ETag</c> response header ("Base64 <c>rowversion</c>.
/// Supply as <c>If-Match</c> on the next mutation."), the wire value is the row's opaque 8-byte
/// <c>rowversion</c>, base64-encoded, then wrapped in double quotes per HTTP's ETag grammar
/// (RFC 9110 §8.8.3: <c>entity-tag = [ weak ] opaque-tag</c>, <c>opaque-tag = DQUOTE *etagc DQUOTE</c>) —
/// a bare, unquoted base64 string is not a spec-compliant ETag.
/// </para>
/// <para>
/// This project only ever emits <b>strong</b> ETags (a <c>rowversion</c> value change means the
/// row genuinely changed — there is no notion of a semantically-equivalent-but-differently-
/// represented byte-for-byte match here, so the weak/strong distinction never applies to what we
/// produce). <see cref="FromIfMatch"/> is nonetheless defensive on the decode side and strips a
/// leading <c>W/</c> prefix if a client echoes one back, since RFC 9110 permits clients to send
/// weak validators in <c>If-Match</c> and we'd rather accept it than 400 on something harmless.
/// </para>
/// <para>
/// Malformed input (missing quotes, non-base64 payload, wrong byte length for a <c>rowversion</c>)
/// throws <see cref="FormatException"/> rather than a generic exception, so T058's endpoint
/// wiring can catch that specific type and turn it into a <c>400</c> instead of letting it bubble
/// to the global <c>ProblemDetails</c> handler as an unhandled <c>500</c>. This helper does not
/// decide HTTP status codes itself — that's T058's concern, per this task's scope.
/// </para>
/// </remarks>
public static class RowVersionETag
{
    /// <summary>
    /// Encodes a <c>rowversion</c> byte array as a quoted, base64-encoded strong ETag header value.
    /// </summary>
    /// <param name="rowVersion">The entity's <c>RowVersion</c> bytes (EF <c>.IsRowVersion()</c>).</param>
    /// <returns>A double-quoted base64 string suitable for the HTTP <c>ETag</c> response header.</returns>
    /// <exception cref="ArgumentNullException"><paramref name="rowVersion"/> is <see langword="null"/>.</exception>
    public static string ToETag(byte[] rowVersion)
    {
        ArgumentNullException.ThrowIfNull(rowVersion);
        return $"\"{Convert.ToBase64String(rowVersion)}\"";
    }

    /// <summary>
    /// Decodes an <c>If-Match</c> header value back to the raw <c>rowversion</c> bytes it encodes,
    /// for use as EF's concurrency-check original value.
    /// </summary>
    /// <param name="ifMatchHeaderValue">
    /// The raw <c>If-Match</c> header value, e.g. <c>"AAAAAAAAB9E="</c>. A leading weak-ETag
    /// <c>W/</c> prefix is tolerated and stripped defensively; this project never emits one.
    /// </param>
    /// <returns>The decoded <c>rowversion</c> bytes.</returns>
    /// <exception cref="ArgumentException"><paramref name="ifMatchHeaderValue"/> is null, empty, or whitespace-only.</exception>
    /// <exception cref="FormatException">
    /// The value is not a properly double-quoted, base64-encoded ETag (this is the exception
    /// T058 should catch and translate to a <c>400</c>).
    /// </exception>
    public static byte[] FromIfMatch(string ifMatchHeaderValue)
    {
        if (string.IsNullOrWhiteSpace(ifMatchHeaderValue))
        {
            throw new ArgumentException("If-Match header value must not be null or empty.", nameof(ifMatchHeaderValue));
        }

        var value = ifMatchHeaderValue.Trim();

        // Defensively tolerate a weak-ETag prefix even though this project only emits strong ETags.
        if (value.StartsWith("W/", StringComparison.Ordinal))
        {
            value = value[2..];
        }

        if (value.Length < 2 || value[0] != '"' || value[^1] != '"')
        {
            throw new FormatException(
                $"Malformed If-Match value '{ifMatchHeaderValue}': expected a double-quoted ETag (e.g. \"<base64>\").");
        }

        var base64 = value[1..^1];

        if (!TryBase64Decode(base64, out var bytes))
        {
            throw new FormatException(
                $"Malformed If-Match value '{ifMatchHeaderValue}': quoted payload is not valid base64.");
        }

        return bytes;
    }

    private static bool TryBase64Decode(string base64, [NotNullWhen(true)] out byte[]? bytes)
    {
        try
        {
            bytes = Convert.FromBase64String(base64);
            return true;
        }
        catch (FormatException)
        {
            bytes = null;
            return false;
        }
    }
}
