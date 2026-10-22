using Tenancy.Domain.Abstractions;

namespace Tenancy.Domain.Invitations;

/// <summary>
/// A pending invitation for a prospective member to join a tenant. Only the SHA-256 hash of the
/// invitation token is stored (<see cref="TokenHash"/>) — the raw token is a credential and is
/// never persisted; hashing is the caller's responsibility.
/// </summary>
/// <remarks>
/// <see cref="InvitationStatus.Expired"/> is a lazily-computed outcome, not a stored transition:
/// <see cref="Accept"/> compares <c>clock.UtcNow</c> against <see cref="ExpiresAtUtc"/> directly
/// and throws <see cref="DomainException"/> without ever writing <see cref="Status"/> to
/// <see cref="InvitationStatus.Expired"/>. This matches data-model.md's note that "Expired is
/// derived, not swept" — the status column is a materialisation for listing, not the source of
/// truth for expiry.
/// </remarks>
public class Invitation : ITenantOwned
{
    private Invitation(
        InvitationId id,
        TenantId tenantId,
        EmailAddress email,
        Role role,
        string tokenHash,
        InvitationStatus status,
        DateTimeOffset expiresAtUtc)
    {
        Id = id;
        TenantId = tenantId;
        Email = email;
        Role = role;
        TokenHash = tokenHash;
        Status = status;
        ExpiresAtUtc = expiresAtUtc;
    }

    /// <summary>
    /// The unique identifier of the invitation.
    /// </summary>
    public InvitationId Id { get; }

    /// <summary>
    /// The ID of the tenant the invitee is being invited to join.
    /// </summary>
    public TenantId TenantId { get; }

    /// <summary>
    /// The email address of the invitee.
    /// </summary>
    public EmailAddress Email { get; }

    /// <summary>
    /// The role the invitee will be granted upon acceptance.
    /// </summary>
    public Role Role { get; }

    /// <summary>
    /// The SHA-256 hash of the invitation token. The raw token is a credential and is never
    /// persisted.
    /// </summary>
    public string TokenHash { get; }

    /// <summary>
    /// The lifecycle state of the invitation.
    /// </summary>
    public InvitationStatus Status { get; private set; }

    /// <summary>
    /// The timestamp after which the invitation can no longer be accepted.
    /// </summary>
    public DateTimeOffset ExpiresAtUtc { get; }

    /// <summary>
    /// Concurrency token maintained by the database (SQL Server <c>rowversion</c>). Never set by
    /// application code — EF Core populates it on read/write.
    /// </summary>
    public byte[] RowVersion { get; private set; } = [];

    /// <summary>
    /// Creates a new, pending invitation for the given email address to join the given tenant
    /// with the given role.
    /// </summary>
    /// <param name="tenantId">The ID of the tenant granting access.</param>
    /// <param name="email">The email address of the invitee.</param>
    /// <param name="role">The role to grant upon acceptance.</param>
    /// <param name="tokenHash">The SHA-256 hash of the invitation token.</param>
    /// <param name="expiresAtUtc">The timestamp after which the invitation can no longer be
    /// accepted.</param>
    public static Invitation Create(
        TenantId tenantId,
        EmailAddress email,
        Role role,
        string tokenHash,
        DateTimeOffset expiresAtUtc)
    {
        return new Invitation(
            InvitationId.New(),
            tenantId,
            email,
            role,
            tokenHash,
            InvitationStatus.Pending,
            expiresAtUtc);
    }

    /// <summary>
    /// Accepts the invitation, transitioning <see cref="Status"/> to
    /// <see cref="InvitationStatus.Accepted"/>.
    /// </summary>
    /// <param name="clock">The clock used to read the current time, injected so the entity — not
    /// the caller — is responsible for reading "now".</param>
    /// <exception cref="DomainException">Thrown if the invitation is not
    /// <see cref="InvitationStatus.Pending"/>, or if <paramref name="clock"/>'s current time is
    /// past <see cref="ExpiresAtUtc"/>. The expiry check never writes <see cref="Status"/> to
    /// <see cref="InvitationStatus.Expired"/> — expiry is derived, not stored.</exception>
    public void Accept(IClock clock)
    {
        if (Status != InvitationStatus.Pending)
        {
            throw new DomainException("Invitation is not pending.");
        }

        if (clock.UtcNow > ExpiresAtUtc)
        {
            throw new DomainException("Invitation has expired.");
        }

        Status = InvitationStatus.Accepted;
    }

    /// <summary>
    /// Revokes the invitation, transitioning <see cref="Status"/> to
    /// <see cref="InvitationStatus.Revoked"/>.
    /// </summary>
    /// <exception cref="DomainException">Thrown if the invitation is not
    /// <see cref="InvitationStatus.Pending"/>.</exception>
    public void Revoke()
    {
        if (Status != InvitationStatus.Pending)
        {
            throw new DomainException("Invitation is not pending.");
        }

        Status = InvitationStatus.Revoked;
    }
}
