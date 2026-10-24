using Identity.Domain.Abstractions;

namespace Identity.Domain.Users;

/// <summary>
/// A user known to the platform, identified for authorization purposes solely by the composite
/// Entra identity <c>(EntraTenantId, EntraObjectId)</c>. <see cref="Email"/> is display and
/// invitation-matching only, and must never be used as an authorization input (research.md R2).
/// </summary>
public class User
{
    private User(UserId id, Guid entraTenantId, Guid entraObjectId, EmailAddress email)
    {
        Id = id;
        EntraTenantId = entraTenantId;
        EntraObjectId = entraObjectId;
        Email = email;
    }

    /// <summary>
    /// The unique identifier of the user.
    /// </summary>
    public UserId Id { get; }

    /// <summary>
    /// The Entra ID tenant identifier from the token's <c>tid</c> claim. Part of the user's
    /// stable, comparable identity for lookup purposes.
    /// </summary>
    public Guid EntraTenantId { get; }

    /// <summary>
    /// The Entra ID object identifier from the token's <c>oid</c> claim. Part of the user's
    /// stable, comparable identity for lookup purposes.
    /// </summary>
    public Guid EntraObjectId { get; }

    /// <summary>
    /// The user's email address. Display and invitation-matching only — never an authorization
    /// input.
    /// </summary>
    public EmailAddress Email { get; }

    /// <summary>
    /// Concurrency token maintained by the database (SQL Server <c>rowversion</c>). Never set by
    /// application code — EF Core populates it on read/write.
    /// </summary>
    public byte[] RowVersion { get; private set; } = [];

    /// <summary>
    /// Creates a new user from the given Entra identity and email.
    /// </summary>
    /// <param name="entraTenantId">The Entra ID tenant identifier (<c>tid</c> claim).</param>
    /// <param name="entraObjectId">The Entra ID object identifier (<c>oid</c> claim).</param>
    /// <param name="email">The user's email address.</param>
    public static User Create(Guid entraTenantId, Guid entraObjectId, EmailAddress email)
    {
        return new User(UserId.New(), entraTenantId, entraObjectId, email);
    }
}
