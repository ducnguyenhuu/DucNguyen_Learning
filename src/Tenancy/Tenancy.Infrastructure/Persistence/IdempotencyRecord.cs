using Tenancy.Domain.Abstractions;

namespace Tenancy.Infrastructure.Persistence;

/// <summary>
/// Caches the outcome of a mutating request so a client-supplied idempotency key (e.g. from an
/// <c>Idempotency-Key</c> header) can be safely retried without double-applying it. This is
/// infrastructure, not a domain entity — it is closer to a cache row than a business object,
/// which is why it lives in <c>Tenancy.Infrastructure</c> rather than <c>Tenancy.Domain</c>.
/// </summary>
/// <remarks>
/// Nothing purges expired rows in this slice. The 24h TTL is honoured only on read: a later
/// application-layer check compares <see cref="CreatedAtUtc"/> against "now" and treats records
/// older than 24h as expired/ignorable. This class does not implement that read-side check —
/// it only documents the intent.
///
/// A background purge job is deliberately out of scope here because it would need explicit
/// tenant context that a scheduled job doesn't naturally have — per this project's
/// <c>distributed-systems</c> skill, a job iterating across ALL tenants' data with no
/// per-request tenant boundary is the most dangerous class of bug in this space. Rows will
/// accumulate until a later roadmap slice adds a tenant-aware purge mechanism.
/// </remarks>
public class IdempotencyRecord : ITenantOwned
{
    /// <summary>
    /// The tenant this idempotency record belongs to. Part of the composite primary key
    /// alongside <see cref="Endpoint"/> and <see cref="Key"/>, and scopes the record so that a
    /// key cannot be probed or replayed across tenants.
    /// </summary>
    public TenantId TenantId { get; set; }

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
    /// The HTTP status code of the original response, replayed verbatim on retry.
    /// </summary>
    public int ResponseStatusCode { get; set; }

    /// <summary>
    /// The cached response body to replay on retry, if any.
    /// </summary>
    public string? ResponseBody { get; set; }

    /// <summary>
    /// When the original request was recorded. Used to determine expiry (24h TTL) on read.
    /// </summary>
    public DateTimeOffset CreatedAtUtc { get; set; }
}
