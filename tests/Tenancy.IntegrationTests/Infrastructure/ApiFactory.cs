using Microsoft.AspNetCore.Authentication;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.Data.SqlClient;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.DependencyInjection.Extensions;
using Respawn;
using Tenancy.Domain.Abstractions;
using Tenancy.Domain.Memberships;
using Tenancy.Domain.Tenants;
using Tenancy.Domain.Users;
using Tenancy.Infrastructure.Persistence;
using Tenancy.Infrastructure.Persistence.Interceptors;

namespace Tenancy.IntegrationTests.Infrastructure;

/// <summary>
/// The shared test host for Tenancy integration tests. Ties together T039
/// (<see cref="SqlServerFixture"/>), T040 (<see cref="TestAuthHandler"/>) and T041
/// (<see cref="SignedTokenHarness"/>) into one running <see cref="WebApplicationFactory{TEntryPoint}"/>.
/// </summary>
/// <remarks>
/// <para>
/// <b>Assembly fixture -&gt; class fixture composition.</b> <see cref="SqlServerFixture"/> is an
/// xUnit v3 <em>assembly</em> fixture (registered via <c>[assembly: AssemblyFixture(typeof(...))]</c>
/// in <c>SqlServerFixture.cs</c>). xUnit v3's own documentation for
/// <c>Xunit.AssemblyFixtureAttribute</c> is explicit about the supported mechanism: "to get access
/// to the instance of the fixture data from inside the test, <b>a constructor argument should be
/// added to the test class</b> which exactly matches the fixture type." That guarantee is scoped
/// to test classes — it does not document (and this project does not rely on) assembly fixtures
/// being resolvable from an arbitrary class fixture's own constructor. Rather than gamble on an
/// unverified fixture-to-fixture DI behavior, this factory takes the documented, guaranteed path:
/// </para>
/// <list type="number">
/// <item>Every test class that uses this factory declares <b>both</b>
/// <c>IClassFixture&lt;ApiFactory&gt;</c> <b>and</b> a constructor parameter of type
/// <see cref="SqlServerFixture"/> (the latter satisfies the documented assembly-fixture
/// injection contract).</item>
/// <item>The test class constructor calls <see cref="UseConnectionString"/> with the fixture's
/// connection string <b>before</b> touching <see cref="WebApplicationFactory{TEntryPoint}.CreateClient"/>
/// or <c>Server</c> (both of which trigger the lazy host build that runs
/// <see cref="ConfigureWebHost"/>).</item>
/// </list>
/// <para>
/// This is exactly the "have <c>ApiFactory</c> itself expose a method/property to receive the
/// connection string post-construction" option flagged in T042's task brief, chosen deliberately
/// over the unverified constructor-injection alternative.
/// </para>
/// <para>
/// <b>Dual auth scheme wiring.</b> Production (<c>Program.cs</c>, T032) registers a single
/// scheme: real JwtBearer under <see cref="JwtBearerDefaults.AuthenticationScheme"/> ("Bearer"),
/// backed by live Entra metadata. Tests need two different things from that one scheme slot:
/// Tier 1 tests (most tests) want <see cref="TestAuthHandler"/>'s zero-network, header-driven
/// identity; Tier 2 tests (T047) want the *real* JwtBearer handler and validation pipeline,
/// fed a controlled signing key instead of live Entra metadata (<see cref="SignedTokenHarness"/>).
/// </para>
/// <para>
/// Both schemes are registered simultaneously — <c>"TestScheme"</c>
/// (<see cref="TestAuthHandler.SchemeName"/>) and <c>"Bearer"</c>
/// (<see cref="JwtBearerDefaults.AuthenticationScheme"/>) — and a third, synthetic
/// <see cref="Microsoft.AspNetCore.Authentication.PolicyScheme"/> named
/// <see cref="PolicySchemeName"/> is installed as the <em>default</em> authenticate/challenge
/// scheme. Its <c>ForwardDefaultSelector</c> inspects the raw <c>Authorization</c> header's
/// scheme prefix on each request and forwards to whichever real scheme matches: a header of
/// <c>"Bearer &lt;jwt&gt;"</c> forwards to the real JwtBearer handler; anything else (including
/// <c>"TestScheme oid=...;tid=..."</c> or any other prefix) forwards to <see cref="TestAuthHandler"/>.
/// This is the "choose via the <c>Authorization</c> header scheme prefix" option from the task
/// brief: a test opts into Tier 2 purely by setting
/// <c>request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", jwt)</c> instead of
/// the Tier 1 <c>X-Test-Oid</c>/<c>X-Test-Tid</c> headers — no per-test host reconfiguration, no
/// second <c>ApiFactory</c> instance, and no risk of the two tiers silently interfering because
/// they are, structurally, two different header shapes routed by one selector.
/// </para>
/// <para>
/// The real JwtBearer scheme's <see cref="Microsoft.IdentityModel.Protocols.ConfigurationManager{T}"/>
/// and <c>Authority</c> are nulled out (per T041's brief) so no live Entra metadata fetch is ever
/// attempted in-process; its
/// <see cref="Microsoft.IdentityModel.Tokens.TokenValidationParameters.IssuerSigningKey"/> is
/// pointed at <see cref="SignedTokenHarness.PublicSigningKey"/>, and issuer/audience validation is
/// pinned to <see cref="ExpectedIssuer"/>/<see cref="ExpectedAudience"/> so T047's tokens can
/// deliberately mismatch those values to exercise the negative-validation paths.
/// </para>
/// </remarks>
public sealed class ApiFactory : WebApplicationFactory<Program>
{
    /// <summary>
    /// Name of the synthetic <c>PolicyScheme</c> installed as the default authenticate/challenge
    /// scheme. See the type-level remarks for the forwarding rule.
    /// </summary>
    public const string PolicySchemeName = "TestPolicyScheme";

    /// <summary>
    /// The <c>ValidIssuer</c> the real JwtBearer scheme is configured to accept in this test
    /// host. <see cref="SignedTokenHarness.MintToken"/> callers should pass this value for the
    /// happy path, and a different value to exercise T047's "wrong issuer" negative case.
    /// </summary>
    public const string ExpectedIssuer = "https://login.microsoftonline.com/test-tenant/v2.0";

    /// <summary>
    /// The <c>ValidAudience</c> the real JwtBearer scheme is configured to accept in this test
    /// host. <see cref="SignedTokenHarness.MintToken"/> callers should pass this value for the
    /// happy path, and a different value to exercise T047's "wrong audience" negative case.
    /// </summary>
    public const string ExpectedAudience = "api://tenancy-test";

    private readonly SignedTokenHarness _tokenHarness = new();

    private string? _connectionString;
    private Respawner? _respawner;

    /// <summary>
    /// Receives the running container's connection string from <see cref="SqlServerFixture"/>
    /// (T039). Must be called by every test class's constructor before this factory's host is
    /// first built (i.e. before <see cref="WebApplicationFactory{TEntryPoint}.CreateClient"/> or
    /// <c>Server</c> is touched) — see the type-level remarks for why this replaces relying on
    /// constructor injection of the assembly fixture directly into <see cref="ApiFactory"/>.
    /// </summary>
    public void UseConnectionString(string connectionString)
    {
        _connectionString = connectionString;
    }

    /// <summary>
    /// The <see cref="SignedTokenHarness"/> this factory configured the real JwtBearer scheme
    /// to trust (via <see cref="SignedTokenHarness.PublicSigningKey"/>). T047 tests mint tokens
    /// from this same instance so the token's signature always matches what the host trusts.
    /// </summary>
    public SignedTokenHarness TokenHarness => _tokenHarness;

    protected override void ConfigureWebHost(IWebHostBuilder builder)
    {
        if (_connectionString is null)
        {
            throw new InvalidOperationException(
                $"{nameof(ApiFactory)}.{nameof(UseConnectionString)} must be called (typically " +
                "from the consuming test class's constructor, using the SqlServerFixture assembly " +
                "fixture injected into that constructor) before the host is built.");
        }

        builder.ConfigureServices(services =>
        {
            // 1. Point TenancyDbContext at the SqlServerFixture container instead of whatever
            // Program.cs would otherwise read from configuration.
            services.RemoveAll<DbContextOptions<TenancyDbContext>>();
            services.AddDbContext<TenancyDbContext>((sp, options) =>
            {
                var interceptor = sp.GetRequiredService<TenantSaveChangesInterceptor>();
                options.UseSqlServer(_connectionString).AddInterceptors(interceptor);
            });

            // 2. Register Tier 1's fake scheme and the forwarding policy scheme described in the
            // type-level remarks, and make the policy scheme the default.
            services.AddAuthentication()
                .AddScheme<AuthenticationSchemeOptions, TestAuthHandler>(TestAuthHandler.SchemeName, options => { })
                .AddPolicyScheme(PolicySchemeName, PolicySchemeName, policyOptions =>
                {
                    policyOptions.ForwardDefaultSelector = context =>
                    {
                        var authorizationHeader = context.Request.Headers.Authorization.ToString();

                        return authorizationHeader.StartsWith("Bearer ", StringComparison.OrdinalIgnoreCase)
                            ? JwtBearerDefaults.AuthenticationScheme
                            : TestAuthHandler.SchemeName;
                    };
                });

            // PostConfigure (not Configure) so this wins regardless of registration order against
            // Program.cs's own AddAuthentication(JwtBearerDefaults.AuthenticationScheme) call.
            services.PostConfigure<AuthenticationOptions>(options =>
            {
                options.DefaultScheme = PolicySchemeName;
                options.DefaultAuthenticateScheme = PolicySchemeName;
                options.DefaultChallengeScheme = PolicySchemeName;
            });

            // 3. Point the real JwtBearer scheme at the SignedTokenHarness's public key instead
            // of live Entra metadata (T041's brief: never fetch OIDC metadata in tests).
            services.Configure<JwtBearerOptions>(JwtBearerDefaults.AuthenticationScheme, options =>
            {
                // Authority null (and MetadataAddress left at its own unset default) means
                // JwtBearerHandler never builds a live ConfigurationManager in the first place —
                // there is no separate ConfigurationManager property to null out (it is
                // non-nullable and unused whenever Authority/MetadataAddress are both absent).
                options.Authority = null;
                options.RequireHttpsMetadata = false;

                options.TokenValidationParameters.ValidateIssuer = true;
                options.TokenValidationParameters.ValidIssuer = ExpectedIssuer;
                options.TokenValidationParameters.ValidateAudience = true;
                options.TokenValidationParameters.ValidAudience = ExpectedAudience;
                options.TokenValidationParameters.ValidateLifetime = true;
                options.TokenValidationParameters.IssuerSigningKey = _tokenHarness.PublicSigningKey;
            });
        });
    }

    /// <summary>
    /// Applies the <c>InitialTenancy</c> migration (T030) against the container's database.
    /// Per T031's project-wide constraint, this must never be replaced with
    /// <c>EnsureCreated()</c> — see <c>TenancyDbContext</c>'s remarks for why.
    /// </summary>
    public async Task InitializeDatabaseAsync()
    {
        using var scope = Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<TenancyDbContext>();
        await db.Database.MigrateAsync();
    }

    /// <summary>
    /// Resets the database to a clean, migrated-but-empty state between tests using Respawn,
    /// rather than re-running migrations (dropping/recreating the schema per test would be far
    /// slower against a single shared container). The <see cref="Respawner"/> itself is built
    /// once and cached, since discovering the schema's reset graph is the expensive part and the
    /// schema does not change between tests.
    /// </summary>
    /// <remarks>
    /// This method exists so test base classes/fixtures (e.g. an <c>IAsyncLifetime.DisposeAsync</c>
    /// hook in a later task) have a reset mechanism to call between tests. No such call site is
    /// wired up yet in this task, since T043 is the first test class.
    /// </remarks>
    public async Task ResetDatabaseAsync()
    {
        if (_connectionString is null)
        {
            throw new InvalidOperationException(
                $"{nameof(UseConnectionString)} must be called before {nameof(ResetDatabaseAsync)}.");
        }

        await using var connection = new SqlConnection(_connectionString);
        await connection.OpenAsync();

        _respawner ??= await Respawner.CreateAsync(connection, new RespawnerOptions
        {
            DbAdapter = DbAdapter.SqlServer,
            TablesToIgnore = ["__EFMigrationsHistory"],
        });

        await _respawner.ResetAsync(connection);
    }

    /// <summary>
    /// Seeds two independent tenants, each with exactly one distinct, active member — the
    /// fixture every cross-tenant isolation test (starting with T043) builds on. Returns enough
    /// identifying information for a test to authenticate as Tenant A's user (via
    /// <see cref="TestAuthHandler"/>'s <c>X-Test-Oid</c>/<c>X-Test-Tid</c> headers, populated from
    /// <see cref="SeededTenant.EntraObjectId"/>/<see cref="SeededTenant.EntraTenantId"/>) and then
    /// attempt to read Tenant B's data using <see cref="SeededTenant.TenantId"/>.
    /// </summary>
    public async Task<TwoTenantSeed> SeedTwoTenantsAsync()
    {
        using var scope = Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<TenancyDbContext>();

        var tenantA = Tenant.Create("Tenant A");
        var tenantB = Tenant.Create("Tenant B");

        var userA = User.Create(
            entraTenantId: Guid.CreateVersion7(),
            entraObjectId: Guid.CreateVersion7(),
            email: new EmailAddress("member-a@tenant-a.example.com"));

        var userB = User.Create(
            entraTenantId: Guid.CreateVersion7(),
            entraObjectId: Guid.CreateVersion7(),
            email: new EmailAddress("member-b@tenant-b.example.com"));

        var membershipA = Membership.Create(tenantA.Id, userA.Id, Role.Member);
        var membershipB = Membership.Create(tenantB.Id, userB.Id, Role.Member);

        db.Tenants.AddRange(tenantA, tenantB);
        db.Users.AddRange(userA, userB);
        db.Memberships.AddRange(membershipA, membershipB);

        await db.SaveChangesAsync();

        return new TwoTenantSeed(
            TenantA: new SeededTenant(tenantA.Id, userA.Id, membershipA.Id, userA.EntraTenantId, userA.EntraObjectId),
            TenantB: new SeededTenant(tenantB.Id, userB.Id, membershipB.Id, userB.EntraTenantId, userB.EntraObjectId));
    }

    /// <inheritdoc />
    protected override void Dispose(bool disposing)
    {
        if (disposing)
        {
            _tokenHarness.Dispose();
        }

        base.Dispose(disposing);
    }
}

/// <summary>
/// A single seeded tenant and its one active member, as produced by
/// <see cref="ApiFactory.SeedTwoTenantsAsync"/>.
/// </summary>
/// <param name="TenantId">The platform tenant aggregate's id.</param>
/// <param name="UserId">The member's platform user id.</param>
/// <param name="MembershipId">The member's active membership id in this tenant.</param>
/// <param name="EntraTenantId">
/// The member's Entra (Azure AD) tenant id — the <c>tid</c> claim value to present when
/// authenticating as this member.
/// </param>
/// <param name="EntraObjectId">
/// The member's Entra object id — the <c>oid</c> claim value to present when authenticating as
/// this member.
/// </param>
public sealed record SeededTenant(
    TenantId TenantId,
    UserId UserId,
    MembershipId MembershipId,
    Guid EntraTenantId,
    Guid EntraObjectId);

/// <summary>
/// Two independent, seeded tenants with distinct members, as produced by
/// <see cref="ApiFactory.SeedTwoTenantsAsync"/>. Tenant A's member is the caller in T043's
/// cross-tenant read attempt against Tenant B.
/// </summary>
public sealed record TwoTenantSeed(SeededTenant TenantA, SeededTenant TenantB);
