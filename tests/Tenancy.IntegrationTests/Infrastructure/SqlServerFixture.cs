using Testcontainers.MsSql;
using Xunit;

[assembly: AssemblyFixture(typeof(Tenancy.IntegrationTests.Infrastructure.SqlServerFixture))]

// All test classes in this assembly share one SQL Server Testcontainer/database (via
// SqlServerFixture's single connection string). Once ResetDatabaseAsync (wired in via
// TenancyIntegrationTestBase.InitializeAsync) truncates every table between tests, letting
// different test classes' collections run in parallel — xUnit v3's default — means one class's
// reset can wipe rows a different, concurrently-running class's test is mid-flight relying on,
// which is far more destructive than the pre-reset leftover-data collisions this whole fix
// exists to solve. Every test class in this assembly implicitly shares state (the database), so
// they must run serialized against each other; only test methods *within* the same class were
// ever safe to interleave, and this project doesn't rely on even that.
[assembly: CollectionBehavior(DisableTestParallelization = true)]

namespace Tenancy.IntegrationTests.Infrastructure;

/// <summary>
/// xUnit v3 assembly fixture that provisions a single SQL Server container shared by every
/// test class in this assembly.
///
/// The image tag is pinned deliberately to <c>2022-latest</c> — see research.md R5. The
/// <c>2025-latest</c> RTM image requires AVX instructions that Rosetta does not implement,
/// which crashes the container on Apple Silicon under emulation. Do not change this tag.
///
/// One container per assembly (not per test class) is required so the platform remains usable
/// under emulation; the assembly-fixture pattern itself guarantees a single shared instance.
/// </summary>
public sealed class SqlServerFixture : IAsyncLifetime
{
    private const string ImageTag = "mcr.microsoft.com/mssql/server:2022-latest";

    private readonly MsSqlContainer _container = new MsSqlBuilder(ImageTag).Build();

    /// <summary>
    /// Connection string to the running SQL Server container. Consumed by <c>ApiFactory</c>
    /// (T042) to point <c>TenancyDbContext</c> at this container for integration tests.
    /// </summary>
    /// <remarks>
    /// Read this fresh (not cached) after calling <see cref="StopAsync"/>/<see cref="StartAsync"/>
    /// — Docker assigns a new random host port on each restart of a stopped container, confirmed
    /// empirically, so the string this returns changes across a stop/start cycle. This is not a
    /// problem for other test classes in the assembly: each one only reads this property (via
    /// <see cref="TenancyIntegrationTestBase"/>'s constructor) when its own <c>ApiFactory</c> is
    /// first built, which — because <c>[assembly: CollectionBehavior(DisableTestParallelization =
    /// true)]</c> above serializes every class against every other — never happens concurrently
    /// with a restart in progress.
    /// </remarks>
    public string ConnectionString => _container.GetConnectionString();

    public async ValueTask InitializeAsync()
    {
        await _container.StartAsync();
    }

    public async ValueTask DisposeAsync()
    {
        await _container.DisposeAsync();
    }

    /// <summary>
    /// Stops the shared container. Exposed only so a readiness-check test can exercise the
    /// "SQL Server unreachable" path against a real container; callers MUST restart it (via
    /// <see cref="StartAsync"/>) in a <c>finally</c> block, since every other test class in this
    /// assembly shares this same container instance.
    /// </summary>
    public Task StopAsync() => _container.StopAsync();

    /// <summary>
    /// Restarts the shared container after <see cref="StopAsync"/>, then blocks until SQL
    /// Server inside it is actually accepting connections before returning.
    /// </summary>
    /// <remarks>
    /// <c>MsSqlBuilder</c>'s built-in wait strategy (an <c>sqlcmd SELECT 1</c> probe) only runs
    /// as part of the container's very first start; a bare <c>_container.StartAsync()</c> after
    /// a stop returns as soon as Docker reports the container running, which can be measurably
    /// before SQL Server itself has finished coming back up inside it — confirmed empirically:
    /// callers that immediately open a connection after a bare restart can hit "connection
    /// refused". Re-running the same probe here closes that gap.
    /// </remarks>
    public async Task StartAsync()
    {
        await _container.StartAsync();

        var deadline = DateTime.UtcNow.AddSeconds(60);
        while (true)
        {
            var result = await _container.ExecAsync(
                ["/opt/mssql-tools18/bin/sqlcmd", "-C", "-Q", "SELECT 1;"]);

            if (result.ExitCode == 0)
            {
                return;
            }

            if (DateTime.UtcNow >= deadline)
            {
                throw new TimeoutException(
                    "SQL Server did not become ready within 60 seconds of restarting the " +
                    "shared Testcontainer.");
            }

            await Task.Delay(TimeSpan.FromSeconds(1));
        }
    }
}
