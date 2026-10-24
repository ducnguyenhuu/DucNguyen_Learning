namespace Identity.Api.Configuration;

/// <summary>
/// Startup-time check backing FR-016/Assumption 7's revocation-staleness trade-off (see
/// <c>RevocationWindowTests</c>, T069): this system performs no per-request token revocation
/// check, so a member removed from a tenant retains access until their already-issued access
/// token expires. The actual token lifetime is configured on the Entra ID app registration (an
/// external system), not here. <see cref="ExpectedMaxLifetimeMinutes"/> in configuration records
/// this API's operational expectation of that lifetime; this class asserts, at boot, that the
/// configured value never silently grows past the one-hour upper bound the spec's trade-off
/// assumes, so a misconfiguration is caught at startup rather than discovered later as a
/// silent security-relevant surprise.
/// </summary>
public static class TokenLifetimeValidation
{
    /// <summary>
    /// The hard upper bound the spec's Assumption 7/FR-016 trade-off is built on: revoked access
    /// must end within one hour without active revocation checks. Any configured expectation
    /// beyond this must be a deliberate, documented reconsideration of that trade-off, not a
    /// silent config drift.
    /// </summary>
    public const int MaxAllowedLifetimeMinutes = 60;

    /// <summary>
    /// Throws if <paramref name="expectedMaxLifetimeMinutes"/> exceeds the one-hour upper bound
    /// FR-016/Assumption 7 relies on. Called from <c>Program.cs</c> before the app starts
    /// accepting requests.
    /// </summary>
    public static void AssertWithinRevocationWindow(int expectedMaxLifetimeMinutes)
    {
        if (expectedMaxLifetimeMinutes > MaxAllowedLifetimeMinutes)
        {
            throw new InvalidOperationException(
                $"TokenLifetime:ExpectedMaxLifetimeMinutes is configured as " +
                $"{expectedMaxLifetimeMinutes} minutes, which exceeds the " +
                $"{MaxAllowedLifetimeMinutes}-minute upper bound that FR-016/Assumption 7 " +
                "relies on. This system does not perform per-request token revocation checks: " +
                "a removed member retains access until their already-issued token expires, and " +
                "this configured value is the upper bound on how long that access window can " +
                "last. It must never silently grow past one hour without a deliberate, " +
                "documented reconsideration of that trade-off.");
        }
    }
}
