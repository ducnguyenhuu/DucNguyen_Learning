using Identity.Domain.Abstractions;

namespace Identity.Infrastructure.Persistence;

/// <summary>
/// Distinguishes an idempotency record whose original request is still being processed from one
/// whose response has been fully captured and is safe to replay. Deliberately infrastructure-only
/// — this does not belong alongside the domain enums in
/// <c>Identity.Domain.Abstractions.Enums</c> because <see cref="IdempotencyRecord"/> itself is a
/// cache row, not a domain entity. Maps to the <c>tinyint</c> column described in data-model.md.
/// </summary>
public enum IdempotencyStatus
{
    /// <summary>The original request is still being processed; no response has been cached yet.</summary>
    InFlight = 0,

    /// <summary>The original request finished; the cached response is safe to replay verbatim.</summary>
    Completed = 1,
}

/// <summary>
/// Caches the outcome of a mutating request so a client-supplied idempotency key (e.g. from an
/// <c>Idempotency-Key</c> header) can be safely retried without double-applying it. This is
/// infrastructure, not a domain entity — it is closer to a cache row than a business object,
/// which is why it lives in <c>Identity.Infrastructure</c> rather than <c>Identity.Domain</c>.
/// </summary>
/// <remarks>
/// <para>
/// The primary key is <c>(CreatedByUserId, Endpoint, Key)</c>: a client-supplied key is scoped to
/// the user who sent it, so two users choosing the same key value never collide, and one user
/// cannot replay another's cached response.
/// </para>
/// <para>
/// Nothing purges expired rows in this slice. The 24h TTL is honoured only on read: a later
/// application-layer check compares <see cref="CreatedAtUtc"/> (or <see cref="ExpiresAtUtc"/>)
/// against "now" and treats records past expiry as expired/ignorable. This class does not
/// implement that read-side check — it only documents the intent.
/// </para>
/// <para>
/// A background purge job is out of scope for this slice; rows accumulate until a later roadmap
/// slice adds one.
/// </para>
/// </remarks>
public class IdempotencyRecord
{
    /// <summary>
    /// Identifies which operation this record applies to, e.g.
    /// <c>"POST /invitations/{token}/accept"</c>.
    /// </summary>
    public string Endpoint { get; set; } = string.Empty;

    /// <summary>
    /// The client-supplied idempotency key, e.g. from an <c>Idempotency-Key</c> header.
    /// </summary>
    public string Key { get; set; } = string.Empty;

    /// <summary>
    /// SHA-256 hash (32 bytes) of the canonicalised request body. Used to detect a client reusing
    /// the same idempotency key with a materially different request body.
    /// </summary>
    public byte[] RequestHash { get; set; } = [];

    /// <summary>
    /// Whether the original request is still being processed (<see cref="IdempotencyStatus.InFlight"/>)
    /// or has finished and is safe to replay (<see cref="IdempotencyStatus.Completed"/>).
    /// </summary>
    public IdempotencyStatus Status { get; set; }

    /// <summary>
    /// The user who made the original request. Part of the composite primary key.
    /// </summary>
    public UserId CreatedByUserId { get; set; }

    /// <summary>
    /// The HTTP status code of the original response, replayed verbatim on retry. Nullable
    /// because it is unknown until the original request completes (<see cref="Status"/> is
    /// <see cref="IdempotencyStatus.Completed"/>); an in-flight record has no status code yet.
    /// </summary>
    public int? StatusCode { get; set; }

    /// <summary>
    /// The cached response body to replay on retry, if any.
    /// </summary>
    public string? ResponseBody { get; set; }

    /// <summary>
    /// The <c>Location</c> header value of the original response, if any, replayed verbatim on
    /// retry (e.g. for a <c>201 Created</c> response).
    /// </summary>
    public string? ResourceLocation { get; set; }

    /// <summary>
    /// When the original request was recorded.
    /// </summary>
    public DateTimeOffset CreatedAtUtc { get; set; }

    /// <summary>
    /// When this record expires (24h TTL from <see cref="CreatedAtUtc"/>) and may be treated as
    /// stale/ignorable on read.
    /// </summary>
    public DateTimeOffset ExpiresAtUtc { get; set; }
}
