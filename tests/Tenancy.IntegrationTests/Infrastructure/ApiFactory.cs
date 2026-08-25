using Microsoft.AspNetCore.Authentication;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.Data.SqlClient;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.DependencyInjection.Extensions;
using Microsoft.Extensions.Logging;
using Respawn;
using Tenancy.Domain.Abstractions;
using Tenancy.Domain.Invitations;
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
    private readonly CapturingLoggerProvider _loggerProvider = new();

    private string? _connectionString;
    private Respawner? _respawner;

    /// <summary>
    /// Every formatted log message the host has produced since construction or since
    /// <see cref="ClearCapturedLogs"/> was last called (T053). See
    /// <see cref="CapturingLoggerProvider"/>'s remarks for why messages are captured as
    /// fully-formatted strings shared across all log categories.
    /// </summary>
    public string[] CapturedLogMessages => _loggerProvider.Messages;

    /// <summary>
    /// Clears previously captured log messages. Because this <see cref="ApiFactory"/> instance
    /// is shared across an entire test class via <c>IClassFixture&lt;ApiFactory&gt;</c>, a test
    /// must call this immediately before the request under test to get a clean, request-scoped
    /// view via <see cref="CapturedLogMessages"/> — otherwise log lines from earlier tests in the
    /// same class would still be present and make hygiene assertions unreliable.
    /// </summary>
    public void ClearCapturedLogs() => _loggerProvider.Clear();

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

        // Registered before ConfigureServices below so every category the host logs from
        // (ASP.NET Core's own request/hosting diagnostics, Microsoft.Identity.Web, etc.) is
        // captured by CapturingLoggerProvider (T053) in addition to whatever providers the host
        // would otherwise use — this augments, it does not replace, default logging.
        builder.ConfigureLogging(logging => logging.AddProvider(_loggerProvider));

        builder.ConfigureServices(services =>
        {
            // 0. Test-only routes (see TestOnlyThrowingEndpoints' remarks) that deliberately let
            // a DomainException/ConflictException reach the global ProblemDetailsHandler
            // unhandled — no real production route can do this today, since every real endpoint
            // already catches those types locally before they would ever reach the handler.
            services.AddSingleton<Microsoft.AspNetCore.Hosting.IStartupFilter, TestOnlyThrowingEndpointsStartupFilter>();

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
            // AuditEntries (T010) has a database trigger that rejects any DELETE outright — the
            // whole point of FR-011's append-only guarantee — so Respawn's reset-via-DELETE would
            // fail against it just like any other caller. It is intentionally excluded from the
            // reset: audit rows accumulate across tests within a shared container instead of being
            // wiped, which is safe today because no test asserts an exact AuditEntries row count;
            // a future test that needs to (e.g. T011's trigger-rejection test) should scope its
            // assertions to rows it itself inserted rather than relying on a clean table.
            TablesToIgnore = ["__EFMigrationsHistory", "AuditEntries"],
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

        // T088: each is the sole member of their own tenant, so — mirroring real
        // CreateTenant/CreateTenantAsync behavior, where the creator becomes Administrator —
        // both are seeded as Administrator rather than Member. Several pre-existing tests using
        // this fixture exercise administrator-only operations (PATCH /tenants/{tenantId}, invite,
        // etc.) that only became role-gated once T088 wired the TenantAdministrator policy;
        // Administrator is a strict superset of what those tests' non-administrator-agnostic
        // assertions (isolation/"not Forbidden" checks) already required, so this does not weaken
        // any existing assertion.
        var membershipA = Membership.Create(tenantA.Id, userA.Id, Role.Administrator);
        var membershipB = Membership.Create(tenantB.Id, userB.Id, Role.Administrator);

        db.Tenants.AddRange(tenantA, tenantB);
        db.Users.AddRange(userA, userB);

        // TenantSaveChangesInterceptor (T017) unconditionally stamps every newly-added
        // ITenantOwned entity's TenantId with the context's ambient CurrentTenantId before it
        // hits the database — it does not trust whatever TenantId the entity was constructed
        // with. CurrentTenantId defaults to TenantId.Empty until something sets it, so batching
        // both memberships into one SaveChangesAsync without setting CurrentTenantId first would
        // silently stamp both with TenantId.Empty instead of tenantA.Id/tenantB.Id, corrupting
        // every membership lookup that follows. Two saves, each preceded by pointing
        // CurrentTenantId at the tenant that membership actually belongs to — the same pattern
        // SeedOneUserInTwoTenantsAsync below already uses for the same reason.
        await db.SaveChangesAsync();

        db.CurrentTenantId = tenantA.Id;
        db.Memberships.Add(membershipA);
        await db.SaveChangesAsync();

        db.CurrentTenantId = tenantB.Id;
        db.Memberships.Add(membershipB);
        await db.SaveChangesAsync();

        return new TwoTenantSeed(
            TenantA: new SeededTenant(tenantA.Id, userA.Id, membershipA.Id, userA.EntraTenantId, userA.EntraObjectId),
            TenantB: new SeededTenant(tenantB.Id, userB.Id, membershipB.Id, userB.EntraTenantId, userB.EntraObjectId));
    }

    /// <summary>
    /// Seeds two independent tenants and <b>one</b> <see cref="User"/> with an active
    /// <see cref="Membership"/> in <b>each</b> tenant — the fixture T049's multi-tenant
    /// membership test builds on. Unlike <see cref="SeedTwoTenantsAsync"/> (distinct members
    /// per tenant), this models a single real user who legitimately belongs to both tenants, so
    /// a test can authenticate once (via <see cref="TestAuthHandler"/>'s
    /// <c>X-Test-Oid</c>/<c>X-Test-Tid</c> headers, populated from
    /// <see cref="SharedUserSeed.EntraTenantId"/>/<see cref="SharedUserSeed.EntraObjectId"/>) and
    /// assert both tenants' data comes back correctly separated, never blended. Both memberships
    /// use <see cref="Role.Member"/>; the role is incidental to this test's isolation concern, so
    /// there's no need for it to vary.
    /// </summary>
    /// <remarks>
    /// <b>Why two <c>SaveChangesAsync</c> calls, each preceded by setting
    /// <see cref="TenancyDbContext.CurrentTenantId"/>.</b> <see cref="TenantSaveChangesInterceptor"/>
    /// (T017's write-side isolation guard) stamps <b>every</b> newly-added <c>ITenantOwned</c>
    /// entity's <c>TenantId</c> with the context's ambient <c>CurrentTenantId</c> before it hits
    /// the database — it does not trust whatever <c>TenantId</c> the caller constructed the
    /// entity with. A single batched save (as <see cref="SeedTwoTenantsAsync"/> does) works there
    /// only because each membership's user is distinct, so the two rows never collide on the
    /// unique <c>(TenantId, UserId)</c> index even when both get stamped with the same ambient
    /// value. Here the same user holds both memberships, so both rows genuinely need different
    /// <c>TenantId</c> values — this seeds each membership in its own save, switching
    /// <see cref="TenancyDbContext.CurrentTenantId"/> in between so the interceptor stamps each
    /// with the tenant it actually belongs to.
    /// </remarks>
    public async Task<OneUserTwoTenantsSeed> SeedOneUserInTwoTenantsAsync()
    {
        using var scope = Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<TenancyDbContext>();

        var tenantX = Tenant.Create("Tenant X");
        var tenantY = Tenant.Create("Tenant Y");

        var sharedUser = User.Create(
            entraTenantId: Guid.CreateVersion7(),
            entraObjectId: Guid.CreateVersion7(),
            email: new EmailAddress("shared-member@multi-tenant.example.com"));

        db.Tenants.AddRange(tenantX, tenantY);
        db.Users.Add(sharedUser);
        await db.SaveChangesAsync();

        db.CurrentTenantId = tenantX.Id;
        var membershipX = Membership.Create(tenantX.Id, sharedUser.Id, Role.Member);
        db.Memberships.Add(membershipX);
        await db.SaveChangesAsync();

        db.CurrentTenantId = tenantY.Id;
        var membershipY = Membership.Create(tenantY.Id, sharedUser.Id, Role.Member);
        db.Memberships.Add(membershipY);
        await db.SaveChangesAsync();

        return new OneUserTwoTenantsSeed(
            TenantX: new TenantMembership(tenantX.Id, "Tenant X", membershipX.Id),
            TenantY: new TenantMembership(tenantY.Id, "Tenant Y", membershipY.Id),
            User: new SharedUserSeed(sharedUser.Id, sharedUser.EntraTenantId, sharedUser.EntraObjectId));
    }

    /// <summary>
    /// Seeds the same two-tenant/two-member fixture as <see cref="SeedTwoTenantsAsync"/>, plus
    /// one genuinely-persisted, still-<see cref="InvitationStatus.Pending"/>
    /// <see cref="Invitation"/> in Tenant B — the fixture T062's invitation-isolation tests
    /// (invite/list/revoke) build on so that a cross-tenant "revoke Tenant B's invitation via
    /// Tenant A's route" attempt targets an invitation id that legitimately exists, rather than
    /// one that is merely absent.
    /// </summary>
    public async Task<TwoTenantSeedWithInvitation> SeedTwoTenantsWithInvitationInTenantBAsync()
    {
        var seed = await SeedTwoTenantsAsync();

        using var scope = Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<TenancyDbContext>();

        db.CurrentTenantId = seed.TenantB.TenantId;

        // The raw token value below must match exactly what UnscopedOperationTests presents on
        // the wire ("some-valid-token-for-tenant-b-invitee") so that AcceptInvitation's real
        // SHA-256-hash-and-lookup (Tenancy.Application.Invitations.InvitationToken) actually
        // resolves this row — a fixed, unrelated placeholder hash here would make every accept
        // attempt silently miss regardless of the presented token, masking both the 403
        // (wrong-identity) and 200 (correct-identity) target-spec assertions those tests make.
        var tokenHashBase64 = Convert.ToBase64String(
            Tenancy.Application.Invitations.InvitationToken.Hash("some-valid-token-for-tenant-b-invitee"));

        var invitation = Invitation.Create(
            seed.TenantB.TenantId,
            new EmailAddress("invitee@tenant-b.example.com"),
            Role.Member,
            tokenHash: tokenHashBase64,
            expiresAtUtc: DateTimeOffset.UtcNow.AddDays(7));
        db.Invitations.Add(invitation);
        await db.SaveChangesAsync();

        return new TwoTenantSeedWithInvitation(seed.TenantA, seed.TenantB, invitation.Id);
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

/// <summary>
/// The same two-tenant/two-member fixture as <see cref="TwoTenantSeed"/>, plus the id of a
/// genuinely-persisted, still-pending <see cref="Invitation"/> that legitimately exists in
/// Tenant B, as produced by <see cref="ApiFactory.SeedTwoTenantsWithInvitationInTenantBAsync"/>.
/// </summary>
public sealed record TwoTenantSeedWithInvitation(
    SeededTenant TenantA,
    SeededTenant TenantB,
    InvitationId InvitationId);

/// <summary>
/// One tenant, and the shared user's active membership id within it, as produced by
/// <see cref="ApiFactory.SeedOneUserInTwoTenantsAsync"/>.
/// </summary>
/// <param name="TenantId">The platform tenant aggregate's id.</param>
/// <param name="DisplayName">The tenant's seeded display name — used by T049's test to assert
/// each <c>GET /tenants/{id}</c> response reflects the correct tenant and never the other one.</param>
/// <param name="MembershipId">The shared user's active membership id in this tenant.</param>
public sealed record TenantMembership(TenantId TenantId, string DisplayName, MembershipId MembershipId);

/// <summary>
/// The single user shared across both tenants in <see cref="OneUserTwoTenantsSeed"/>, identified
/// by the Entra claims a test presents via <see cref="TestAuthHandler"/>'s headers.
/// </summary>
/// <param name="UserId">The shared member's platform user id.</param>
/// <param name="EntraTenantId">The <c>tid</c> claim value to present when authenticating as this
/// user.</param>
/// <param name="EntraObjectId">The <c>oid</c> claim value to present when authenticating as this
/// user.</param>
public sealed record SharedUserSeed(UserId UserId, Guid EntraTenantId, Guid EntraObjectId);

/// <summary>
/// Two independent tenants sharing one active member, as produced by
/// <see cref="ApiFactory.SeedOneUserInTwoTenantsAsync"/>. The shared <see cref="User"/>
/// authenticates once and is expected to operate against each tenant in turn, with each
/// response reflecting only that tenant's own data (FR-010).
/// </summary>
public sealed record OneUserTwoTenantsSeed(TenantMembership TenantX, TenantMembership TenantY, SharedUserSeed User);
