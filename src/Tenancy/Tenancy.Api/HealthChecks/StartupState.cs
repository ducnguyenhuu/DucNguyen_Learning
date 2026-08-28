namespace Tenancy.Api.HealthChecks;

/// <summary>
/// Tracks whether this process's own startup work (dev-time migrations, any future warm-up
/// step) has finished, independent of any dependency's reachability. Backs
/// <see cref="StartupHealthCheck"/>, which is what gives FR-008's "not-yet-ready" state — distinct
/// from "healthy" and from "unhealthy (dependency down)" — an actual signal to report on
/// <c>/health/ready</c>.
/// </summary>
/// <remarks>
/// Registered as a singleton: startup completion is a process-wide fact, not a per-request one.
/// <see cref="MarkReady"/> is expected to be called exactly once, from <c>Program.cs</c>, after
/// all startup work has finished and before <c>app.Run()</c> starts accepting requests in
/// earnest. Reads/writes to <see cref="IsReady"/> go through a <c>volatile</c> field so a write on
/// one thread is visible to health-check evaluations running on another without needing a lock —
/// the field is a single bool, so no read/modify/write race is possible.
/// </remarks>
public sealed class StartupState
{
    private volatile bool _isReady;

    public bool IsReady => _isReady;

    public void MarkReady() => _isReady = true;
}
