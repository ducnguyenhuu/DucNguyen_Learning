using Xunit;

namespace Identity.IntegrationTests.Infrastructure;

/// <summary>
/// Shared base class for every Identity integration test class, wiring
/// <see cref="ApiFactory.ResetDatabaseAsync"/> into the per-test lifecycle so each
/// <c>[Fact]</c>/<c>[Theory]</c> method starts against a clean, migrated-but-empty database
/// instead of whatever rows earlier tests (in this class or any other class sharing the
/// container) happened to leave behind.
/// </summary>
/// <remarks>
/// <para>
/// <b>Why this exists.</b> <see cref="ApiFactory"/> is registered per test class via
/// <c>IClassFixture&lt;ApiFactory&gt;</c> and is shared across every test method in that class;
/// its own <see cref="ApiFactory.ResetDatabaseAsync"/> method had never been wired into any
/// call site (see that method's remarks). All test classes also share the single SQL Server
/// Testcontainer started by the assembly-level <see cref="SqlServerFixture"/>. Combined with
/// xUnit v3 on Microsoft.Testing.Platform not guaranteeing ordering (or isolation) between test
/// classes/methods, tests that seed fixed, predictable data (specific emails, tokens,
/// names) can collide with leftover rows a different test left behind earlier in the same
/// process run — a genuine source of non-deterministic failures, not a flaw in the tests
/// themselves.
/// </para>
/// <para>
/// <b>Why a base class, not a "true" zero-touch mechanism.</b> xUnit v3 instantiates a new
/// instance of the test class for every test method, so <see cref="IAsyncLifetime.InitializeAsync"/>
/// on the test class itself runs before <em>each</em> test method — exactly the granularity a
/// reset needs. <see cref="ApiFactory"/>, by contrast, is a <em>class</em> fixture: xUnit
/// constructs it once per test class (not per method), so any lifecycle hook implemented
/// directly on <see cref="ApiFactory"/> only runs once per class, too coarse for a per-test
/// reset. The only hook that runs once per test method is the test class's own
/// <see cref="IAsyncLifetime"/>, which necessarily means the test class itself has to
/// participate — there is no assembly- or fixture-level mechanism in xUnit v3 that reaches into
/// a shared class fixture on a per-method cadence without the consuming class doing something.
/// A shared base class is the smallest form that "something" can take: every existing test
/// class already declares the same <c>(SqlServerFixture, ApiFactory)</c> constructor shape (see
/// <see cref="ApiFactory"/>'s type-level remarks), so switching each class from implementing
/// <c>IClassFixture&lt;ApiFactory&gt;</c> directly to extending this base class is a
/// mechanical, one-line-per-file change with no behavioral change to any test body.
/// </para>
/// <para>
/// <b>Ordering.</b> <see cref="InitializeAsync"/> resets the database <em>before</em> the test
/// method calls <see cref="ApiFactory.InitializeDatabaseAsync"/> (migrate) and any
/// <c>Seed*Async</c> helper, both of which existing test methods already call as their own first
/// lines — reset-then-migrate-then-seed is safe because migrating an already-migrated schema is
/// a no-op, and it guarantees every test's seed data lands in a table set with zero rows left
/// over from any other test.
/// </para>
/// </remarks>
public abstract class IdentityIntegrationTestBase : IClassFixture<ApiFactory>, IAsyncLifetime
{
    /// <summary>
    /// The shared, per-test-class <see cref="ApiFactory"/> instance. Protected so derived test
    /// classes can use it exactly as they used to use their own private <c>_factory</c> field.
    /// </summary>
    protected ApiFactory Factory { get; }

    /// <summary>
    /// Points <see cref="Factory"/> at the shared container's connection string. Must happen in
    /// the constructor (before the host is ever built) — see <see cref="ApiFactory"/>'s
    /// type-level remarks for why this cannot be deferred to <see cref="InitializeAsync"/>.
    /// </summary>
    protected IdentityIntegrationTestBase(SqlServerFixture sqlServerFixture, ApiFactory factory)
    {
        Factory = factory;
        Factory.UseConnectionString(sqlServerFixture.ConnectionString);
    }

    /// <summary>
    /// Runs before every test method (xUnit v3 constructs a fresh test class instance per
    /// method, so this — unlike anything hosted on the shared <see cref="ApiFactory"/> class
    /// fixture — genuinely runs at per-test granularity). Migrates the database (a no-op once
    /// the schema already exists, but required before the very first test in the whole run,
    /// since nothing else guarantees the schema exists yet at that point) and then resets it via
    /// <see cref="ApiFactory.ResetDatabaseAsync"/>, so each test starts from a clean, empty,
    /// migrated schema regardless of what any earlier test (in this class or another) left
    /// behind.
    /// </summary>
    public virtual async ValueTask InitializeAsync()
    {
        await Factory.InitializeDatabaseAsync();
        await Factory.ResetDatabaseAsync();
    }

    /// <inheritdoc />
    public virtual ValueTask DisposeAsync() => default;
}
