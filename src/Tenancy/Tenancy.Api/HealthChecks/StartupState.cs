namespace Tenancy.Api.HealthChecks;

/// <summary>
/// Tracks this process's readiness lifecycle: not-yet-started, ready, and draining. Backs
/// <see cref="StartupHealthCheck"/>, which is what gives <c>/health/ready</c> three
/// distinguishable states instead of the two <see cref="Microsoft.Extensions.Diagnostics.HealthChecks.HealthStatus"/>
/// naturally offers for this purpose (data-model.md §1).
/// </summary>
/// <remarks>
/// Registered as a singleton: readiness is a process-wide fact, not a per-request one.
/// <see cref="MarkReady"/> is expected to be called exactly once, from <c>Program.cs</c>, after
/// all startup work has finished; <see cref="MarkStopping"/> is called exactly once, from the
/// <c>IHostApplicationLifetime.ApplicationStopping</c> callback. Transitions are one-way and
/// terminal at draining — <c>Starting -&gt; Ready -&gt; Draining</c> and also
/// <c>Starting -&gt; Draining</c> (a termination signal arriving before readiness). A single
/// <c>volatile</c> field is sufficient without a lock because every transition here is a
/// single write; <see cref="MarkReady"/> additionally guards against the one real race — a
/// late-arriving readiness signal must not resurrect readiness after stopping has already
/// been marked.
/// </remarks>
public sealed class StartupState
{
    private const int Starting = 0;
    private const int Ready = 1;
    private const int Draining = 2;

    // An int, not the enum directly: Interlocked.CompareExchange has no enum overload, and
    // MarkReady's transition is a read-modify-write (see remarks above) that a plain
    // volatile field cannot make atomic on its own.
    private int _phase = Starting;

    public bool IsReady => Volatile.Read(ref _phase) == Ready;

    public bool IsDraining => Volatile.Read(ref _phase) == Draining;

    public void MarkReady()
    {
        // Only advance from Starting. If MarkStopping already ran (Draining), this must not
        // resurrect readiness — the one real hazard data-model.md §1 calls out.
        Interlocked.CompareExchange(ref _phase, Ready, Starting);
    }

    public void MarkStopping() => Volatile.Write(ref _phase, Draining);
}
