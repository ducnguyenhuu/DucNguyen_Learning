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
/// <b>Deliberate exception to the <c>ITenantOwned</c> auto-filter pattern (ADR-017 exception
/// 1):</b> <c>POST /tenants</c> — the request that creates the very first tenant for a user — has
/// no tenant context yet when its idempotency record is written. SQL Server's composite primary
/// key <c>(TenantId, CreatedByUserId, Endpoint, Key)</c> cannot hold a <c>NULL</c> in any key
/// column (no per-column exception exists for a column participating in a PK), so
/// <see cref="TenantId"/> uses the fixed sentinel <c>TenantId.Empty</c> for the pre-tenant case
/// rather than a nullable CLR type — a <c>TenantId?</c> is silently discarded by EF Core's model
/// builder once the property participates in <c>HasKey(...)</c> anyway, generating a plain
/// non-nullable column regardless of the CLR type. <see cref="CreatedByUserId"/> — always real,
/// never sentinel — is what actually disambiguates two different users both calling
/// <c>POST /tenants</c> with the same client-supplied idempotency key value; the sentinel
/// <see cref="TenantId"/> is just a fixed placeholder so the PK column stays non-null. Because of
/// this, this class intentionally does <b>not</b> implement <see cref="ITenantOwned"/> and
/// therefore does not participate in <c>IdentityDbContext</c>'s automatic <c>"TenantFilter"</c>
/// global query filter that every other tenant-owned entity gets for free. This is a one-off,
/// reasoned exception, not an oversight: any future code that queries this entity MUST apply its
/// own explicit filter — either <c>TenantId == tenantId</c> for the normal, tenant-scoped case,
/// or <c>TenantId == TenantId.Empty &amp;&amp; CreatedByUserId == userId</c> for the pre-tenant
/// <c>POST /tenants</c> case — to avoid leaking or colliding idempotency records across
/// tenants/users.
/// </para>
/// <para>
/// Nothing purges expired rows in this slice. The 24h TTL is honoured only on read: a later
/// application-layer check compares <see cref="CreatedAtUtc"/> (or <see cref="ExpiresAtUtc"/>)
/// against "now" and treats records past expiry as expired/ignorable. This class does not
/// implement that read-side check — it only documents the intent.
/// </para>
/// <para>
/// A background purge job is deliberately out of scope here because it would need explicit
/// tenant context that a scheduled job doesn't naturally have — per this project's
/// <c>distributed-systems</c> skill, a job iterating across ALL tenants' data with no per-request
/// tenant boundary is the most dangerous class of bug in this space. Rows will accumulate until a
/// later roadmap slice adds a tenant-aware purge mechanism.
/// </para>
/// </remarks>
public class IdempotencyRecord
{
    /// <summary>
    /// The tenant this idempotency record belongs to, or <see cref="Domain.Abstractions.TenantId.Empty"/>
    /// (a fixed sentinel, never a real tenant) when the original request (e.g. <c>POST /tenants</c>)
    /// had no tenant context yet. Part of the composite primary key alongside
    /// <see cref="CreatedByUserId"/>, <see cref="Endpoint"/>, and <see cref="Key"/>. See the class
    /// remarks for why this entity does not implement <c>ITenantOwned</c> and is not
    /// auto-filtered by tenant.
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
    /// The user who made the original request. Always the real caller's id (never a sentinel) —
    /// part of the composite primary key, and the real disambiguator when <see cref="TenantId"/>
    /// is the sentinel <see cref="Domain.Abstractions.TenantId.Empty"/> (the pre-tenant
    /// <c>POST /tenants</c> case).
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
