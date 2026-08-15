namespace Tenancy.Domain.Abstractions;

/// <summary>
/// Value object representing an email address, normalised to lowercase at construction.
/// Used for display and for exact-match invitation lookups — never as an authorization input.
/// Identity for authorization purposes is always the composite (EntraTenantId, EntraObjectId).
/// </summary>
public readonly record struct EmailAddress
{
    /// <summary>
    /// Gets the normalised (lowercase) email address value.
    /// </summary>
    public string Value { get; }

    /// <summary>
    /// Initializes a new instance of the <see cref="EmailAddress"/> struct, validating and
    /// normalising the supplied value.
    /// </summary>
    /// <param name="value">The raw email address string.</param>
    /// <exception cref="DomainException">
    /// Thrown when <paramref name="value"/> is null, whitespace-only, or does not contain an
    /// '@' character.
    /// </exception>
    public EmailAddress(string value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            throw new DomainException("Email address cannot be null or whitespace.");
        }

        if (!value.Contains('@'))
        {
            throw new DomainException($"'{value}' is not a valid email address: missing '@'.");
        }

        Value = value.ToLowerInvariant();
    }

    /// <summary>
    /// Returns the normalised email address value.
    /// </summary>
    public override string ToString() => Value;
}
