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
    public string ConnectionString => _container.GetConnectionString();

    public async ValueTask InitializeAsync()
    {
        await _container.StartAsync();
    }

    public async ValueTask DisposeAsync()
    {
        await _container.DisposeAsync();
    }
}
