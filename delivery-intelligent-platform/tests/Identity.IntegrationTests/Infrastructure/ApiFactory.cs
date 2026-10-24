using Microsoft.AspNetCore.Authentication;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.Data.SqlClient;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.DependencyInjection.Extensions;
using Microsoft.Extensions.Logging;
using Respawn;
using Identity.Domain.Abstractions;
using Identity.Domain.Invitations;
using Identity.Domain.Memberships;
using Identity.Domain.Users;
using Identity.Infrastructure.Observability;
using Identity.Infrastructure.Persistence;

namespace Identity.IntegrationTests.Infrastructure;

/// <summary>
/// The shared test host for Identity integration tests. Ties together
/// <see cref="SqlServerFixture"/>, <see cref="TestAuthHandler"/> and
/// <see cref="SignedTokenHarness"/> into one running <see cref="WebApplicationFactory{TEntryPoint}"/>.
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
/// connection string post-construction" option, chosen deliberately over the unverified
/// constructor-injection alternative.
/// </para>
/// <para>
/// <b>Dual auth scheme wiring.</b> Production (<c>Program.cs</c>) registers a single
/// scheme: real JwtBearer under <see cref="JwtBearerDefaults.AuthenticationScheme"/> ("Bearer"),
/// backed by live Entra metadata. Tests need two different things from that one scheme slot:
/// Tier 1 tests (most tests) want <see cref="TestAuthHandler"/>'s zero-network, header-driven
/// identity; Tier 2 tests (the signed-token negative-validation tests) want the *real* JwtBearer
/// handler and validation pipeline, fed a controlled signing key instead of live Entra metadata
/// (<see cref="SignedTokenHarness"/>).
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
/// This is the "choose via the <c>Authorization</c> header scheme prefix" option: a test opts
/// into Tier 2 purely by setting
/// <c>request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", jwt)</c> instead of
/// the Tier 1 <c>X-Test-Oid</c>/<c>X-Test-Tid</c> headers — no per-test host reconfiguration, no
/// second <c>ApiFactory</c> instance, and no risk of the two tiers silently interfering because
/// they are, structurally, two different header shapes routed by one selector.
/// </para>
/// <para>
/// The real JwtBearer scheme's <see cref="Microsoft.IdentityModel.Protocols.ConfigurationManager{T}"/>
/// and <c>Authority</c> are nulled out so no live Entra metadata fetch is ever attempted
/// in-process; its
/// <see cref="Microsoft.IdentityModel.Tokens.TokenValidationParameters.IssuerSigningKey"/> is
/// pointed at <see cref="SignedTokenHarness.PublicSigningKey"/>, and issuer/audience validation is
/// pinned to <see cref="ExpectedIssuer"/>/<see cref="ExpectedAudience"/> so the negative-validation
/// tests can deliberately mismatch those values to exercise those paths.
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
    /// happy path, and a different value to exercise the "wrong issuer" negative case.
    /// </summary>
    public const string ExpectedIssuer = "https://login.microsoftonline.com/test-tenant/v2.0";

    /// <summary>
    /// The <c>ValidAudience</c> the real JwtBearer scheme is configured to accept in this test
    /// host. <see cref="SignedTokenHarness.MintToken"/> callers should pass this value for the
    /// happy path, and a different value to exercise the "wrong audience" negative case.
    /// </summary>
    public const string ExpectedAudience = "api://identity-test";

    private readonly SignedTokenHarness _tokenHarness = new();
    private readonly CapturingLoggerProvider _loggerProvider = new();

    private string? _connectionString;
    private Respawner? _respawner;
    private string? _otlpEndpointOverride;

    /// <summary>
    /// Every formatted log message the host has produced since construction or since
    /// <see cref="ClearCapturedLogs"/> was last called. See
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
    /// Receives the running container's connection string from <see cref="SqlServerFixture"/>.
    /// Must be called by every test class's constructor before this factory's host is
    /// first built (i.e. before <see cref="WebApplicationFactory{TEntryPoint}.CreateClient"/> or
    /// <c>Server</c> is touched) — see the type-level remarks for why this replaces relying on
    /// constructor injection of the assembly fixture directly into <see cref="ApiFactory"/>.
    /// </summary>
    public void UseConnectionString(string connectionString)
    {
        _connectionString = connectionString;
    }

    /// <summary>
    /// Test-only hook that points the OTLP exporter at a specific endpoint instead of
    /// whatever <c>OTEL_EXPORTER_OTLP_ENDPOINT</c>/the SDK default would otherwise resolve to.
    /// Used by <c>TelemetryResilienceTests</c> to point the exporter at an address nothing is
    /// listening on, so a normal request can be proven not to fail, block, or slow down when the
    /// telemetry backend is unreachable (FR-006). Must be called (like
    /// <see cref="UseConnectionString"/>) before the host is first built.
    /// </summary>
    public void UseOtlpEndpoint(string endpoint)
    {
        _otlpEndpointOverride = endpoint;
    }

    /// <summary>
    /// The <see cref="SignedTokenHarness"/> this factory configured the real JwtBearer scheme
    /// to trust (via <see cref="SignedTokenHarness.PublicSigningKey"/>). Tier 2 tests mint tokens
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

        if (_otlpEndpointOverride is not null)
        {
            builder.ConfigureAppConfiguration(configBuilder => configBuilder.AddInMemoryCollection(
                new Dictionary<string, string?>
                {
                    [OpenTelemetryExtensions.OtlpEndpointConfigurationKey] = _otlpEndpointOverride,
                }));
        }

        // Registered before ConfigureServices below so every category the host logs from
        // (ASP.NET Core's own request/hosting diagnostics, Microsoft.Identity.Web, etc.) is
        // captured by CapturingLoggerProvider in addition to whatever providers the host
        // would otherwise use — this augments, it does not replace, default logging.
        builder.ConfigureLogging(logging => logging.AddProvider(_loggerProvider));

        builder.ConfigureServices(services =>
        {
            // 0. Test-only routes (see TestOnlyThrowingEndpoints' remarks) that deliberately let
            // a DomainException/ConflictException reach the global ProblemDetailsHandler
            // unhandled — no real production route can do this today, since every real endpoint
            // already catches those types locally before they would ever reach the handler.
            services.AddSingleton<Microsoft.AspNetCore.Hosting.IStartupFilter, TestOnlyThrowingEndpointsStartupFilter>();

            // 1. Point IdentityDbContext at the SqlServerFixture container instead of whatever
            // Program.cs would otherwise read from configuration.
            services.RemoveAll<DbContextOptions<IdentityDbContext>>();
            services.AddDbContext<IdentityDbContext>(options => options.UseSqlServer(_connectionString));

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
            // of live Entra metadata — tests never fetch OIDC metadata.
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
    /// Applies the <c>InitialIdentity</c> migration against the container's database.
    /// Per this project's constraint on schema setup, this must never be replaced with
    /// <c>EnsureCreated()</c> — see <c>IdentityDbContext</c>'s remarks for why.
    /// </summary>
    public async Task InitializeDatabaseAsync()
    {
        using var scope = Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<IdentityDbContext>();
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
    /// hook) have a reset mechanism to call between tests.
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
            // AuditEntries has a database trigger that rejects any DELETE outright — the
            // whole point of FR-011's append-only guarantee — so Respawn's reset-via-DELETE would
            // fail against it just like any other caller. It is intentionally excluded from the
            // reset: audit rows accumulate across tests within a shared container instead of being
            // wiped, which is safe because no test asserts an exact AuditEntries row count;
            // any trigger-rejection test should scope its assertions to rows it itself inserted
            // rather than relying on a clean table.
            TablesToIgnore = ["__EFMigrationsHistory", "AuditEntries"],
        });

        await _respawner.ResetAsync(connection);
    }

    /// <summary>
    /// Seeds one <see cref="User"/> with an active <see cref="Membership"/> holding
    /// <paramref name="role"/> in the organization, and returns what a test needs to authenticate
    /// as them (<see cref="CreateClientFor"/>) and to target them by id.
    /// </summary>
    /// <remarks>
    /// Each call creates a distinct user with fresh Entra <c>(tid, oid)</c> values, so a test
    /// builds the exact cast it needs — say one Administrator and one Reader — by calling this once
    /// per member. When <paramref name="email"/> is omitted a unique address is generated, so two
    /// seeded members never collide on the user table's unique email lookups.
    /// </remarks>
    public async Task<SeededMember> SeedMemberAsync(Role role, string? email = null)
    {
        using var scope = Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<IdentityDbContext>();

        var user = User.Create(
            entraTenantId: Guid.CreateVersion7(),
            entraObjectId: Guid.CreateVersion7(),
            email: new EmailAddress(email ?? $"{role.ToString().ToLowerInvariant()}-{Guid.NewGuid():N}@example.com"));
        var membership = Membership.Create(user.Id, role);

        db.Users.Add(user);
        db.Memberships.Add(membership);
        await db.SaveChangesAsync();

        return new SeededMember(user.Id, membership.Id, user.EntraTenantId, user.EntraObjectId, user.Email.Value);
    }

    /// <summary>
    /// Seeds a persisted <see cref="Invitation"/> for <paramref name="email"/> whose stored token
    /// hash is the real hash of <paramref name="rawToken"/>, so presenting <paramref name="rawToken"/>
    /// to <c>POST /invitations/{token}/accept</c> genuinely resolves this row. Optionally moves it
    /// out of <see cref="InvitationStatus.Pending"/> first (<see cref="InvitationStatus.Revoked"/>
    /// or <see cref="InvitationStatus.Accepted"/>), for the refusal tests that need a token that
    /// exists but can no longer be used.
    /// </summary>
    /// <remarks>
    /// Accepting is done through <see cref="Invitation.Accept"/> with a clock pinned before the
    /// expiry, so a test can seed an invitation that is both accepted and expired without the
    /// domain refusing the transition.
    /// </remarks>
    public async Task<InvitationId> SeedInvitationAsync(
        string email,
        Role role,
        string rawToken,
        DateTimeOffset expiresAtUtc,
        InvitationStatus status = InvitationStatus.Pending)
    {
        using var scope = Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<IdentityDbContext>();

        var invitation = Invitation.Create(
            new EmailAddress(email),
            role,
            tokenHash: Convert.ToBase64String(Identity.Application.Invitations.InvitationToken.Hash(rawToken)),
            expiresAtUtc);

        switch (status)
        {
            case InvitationStatus.Pending:
                break;
            case InvitationStatus.Revoked:
                invitation.Revoke();
                break;
            case InvitationStatus.Accepted:
                invitation.Accept(new FixedClock(expiresAtUtc.AddMinutes(-1)));
                break;
            default:
                throw new ArgumentOutOfRangeException(
                    nameof(status), status, "Expired is derived from ExpiresAtUtc, never stored.");
        }

        db.Invitations.Add(invitation);
        await db.SaveChangesAsync();

        return invitation.Id;
    }

    /// <summary>
    /// The <c>If-Match</c> value for <paramref name="membershipId"/>'s current, persisted
    /// <c>RowVersion</c>. <c>PATCH</c>/<c>DELETE /members/{userId}</c> require a genuine
    /// precondition (FR-021), and <c>GET /members</c> exposes no per-member ETag to round-trip
    /// through HTTP instead.
    /// </summary>
    public async Task<string> GetMembershipIfMatchAsync(MembershipId membershipId)
    {
        using var scope = Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<IdentityDbContext>();
        var membership = await db.Memberships.AsNoTracking().SingleAsync(m => m.Id == membershipId);
        return Identity.Api.ETags.RowVersionETag.ToETag(membership.RowVersion);
    }

    /// <summary>
    /// A client authenticated (Tier 1, <see cref="TestAuthHandler"/>) as the identity with the
    /// given Entra <c>(tid, oid)</c>. The token kind defaults to a signed-in user's delegated
    /// scope; callers add <c>X-Test-Roles</c>/<c>X-Test-Scp</c> themselves to model something
    /// else.
    /// </summary>
    public HttpClient CreateClientFor(Guid entraTenantId, Guid entraObjectId)
    {
        var client = CreateClient();
        client.DefaultRequestHeaders.Authorization =
            new System.Net.Http.Headers.AuthenticationHeaderValue(TestAuthHandler.SchemeName, "test");
        client.DefaultRequestHeaders.Add("X-Test-Oid", entraObjectId.ToString());
        client.DefaultRequestHeaders.Add("X-Test-Tid", entraTenantId.ToString());
        return client;
    }

    /// <summary>A client authenticated as <paramref name="member"/>; see
    /// <see cref="CreateClientFor(Guid, Guid)"/>.</summary>
    public HttpClient CreateClientFor(SeededMember member) =>
        CreateClientFor(member.EntraTenantId, member.EntraObjectId);

    /// <summary>
    /// A client authenticated as a brand-new identity that has never been seen before: no user
    /// row, no membership. The non-member every member-only route must refuse with 403.
    /// </summary>
    public HttpClient CreateClientForStranger() =>
        CreateClientFor(Guid.NewGuid(), Guid.NewGuid());

    /// <inheritdoc />
    protected override void Dispose(bool disposing)
    {
        if (disposing)
        {
            _tokenHarness.Dispose();
        }

        base.Dispose(disposing);
    }

    /// <summary>An <see cref="IClock"/> that always reports one instant, for seeding only.</summary>
    private sealed class FixedClock(DateTimeOffset utcNow) : IClock
    {
        public DateTimeOffset UtcNow { get; } = utcNow;
    }
}

/// <summary>
/// One seeded member of the organization, as produced by <see cref="ApiFactory.SeedMemberAsync"/>.
/// </summary>
/// <param name="UserId">The member's platform user id — the <c>{userId}</c> in
/// <c>/members/{userId}</c>.</param>
/// <param name="MembershipId">The member's active membership id.</param>
/// <param name="EntraTenantId">The member's Entra directory id — the <c>tid</c> claim value to
/// present when authenticating as them. This is the identity provider's directory (ADR-019), not
/// application tenancy.</param>
/// <param name="EntraObjectId">The member's Entra object id — the <c>oid</c> claim value to
/// present when authenticating as them.</param>
/// <param name="Email">The member's seeded email address.</param>
public sealed record SeededMember(
    UserId UserId,
    MembershipId MembershipId,
    Guid EntraTenantId,
    Guid EntraObjectId,
    string Email);
