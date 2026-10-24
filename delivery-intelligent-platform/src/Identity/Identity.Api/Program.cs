using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.AspNetCore.Authorization;
using Microsoft.EntityFrameworkCore;
using Microsoft.Identity.Web;
using Identity.Api.Authorization;
using Identity.Api.Configuration;
using Identity.Api.Endpoints;
using Identity.Api.ErrorHandling;
using Identity.Api.HealthChecks;
using Identity.Api.Middleware;
using Microsoft.AspNetCore.Diagnostics.HealthChecks;
using Identity.Application.Abstractions;
using Identity.Application.Tenants;
using Identity.Application.Users;
using Identity.Domain.Abstractions;
using Identity.Infrastructure.Observability;
using Identity.Infrastructure.Persistence;
using Identity.Infrastructure.Persistence.Audited;
using Identity.Infrastructure.Persistence.Interceptors;
using Identity.Infrastructure.Security;

var builder = WebApplication.CreateBuilder(args);

// Assumption 7's revocation-staleness trade-off, made an operationally checked
// expectation rather than a design note nobody will find later (see RevocationWindowTests
// and TokenLifetimeValidation's remarks): this API performs no per-request token
// revocation check, so a member removed from a tenant retains access until their already-issued
// token expires. The actual token lifetime is set on the Entra ID app registration (external to
// this codebase) — TokenLifetime:ExpectedMaxLifetimeMinutes below just records this system's
// operational expectation of that value. Fail fast at boot, before accepting any requests, if
// that expectation has silently grown past the one-hour bound the trade-off assumes.
var expectedMaxLifetimeMinutes = builder.Configuration.GetValue<int>(
    "TokenLifetime:ExpectedMaxLifetimeMinutes");
TokenLifetimeValidation.AssertWithinRevocationWindow(expectedMaxLifetimeMinutes);

// Add services to the container.
// Learn more about configuring OpenAPI at https://aka.ms/aspnet/openapi
builder.Services.AddOpenApi();

builder.Services.AddIdentityObservability(builder.Configuration);

// RFC 9457 global error handling: AddExceptionHandler alone is not sufficient —
// AddProblemDetails() supplies the ProblemDetails-writing infrastructure that the exception
// handler middleware (registered below via UseExceptionHandler()) relies on, and
// ProblemDetailsHandler is where the actual "never leak exception.Message/StackTrace/type"
// contract is enforced. All three pieces (AddExceptionHandler + AddProblemDetails +
// UseExceptionHandler) are required together for this to take effect.
builder.Services.AddExceptionHandler<ProblemDetailsHandler>();
builder.Services.AddProblemDetails();

// Entra ID (Azure AD) bearer-token authentication. The "AzureAd" configuration section
// (tenant/client IDs, etc.) is populated via User Secrets; this only wires the scheme.
builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
    .AddMicrosoftIdentityWebApi(builder.Configuration.GetSection("AzureAd"));

// By default, ASP.NET Core's JWT handler remaps standard OIDC claim names (e.g. "oid" ->
// "http://schemas.microsoft.com/identity/claims/objectidentifier") into legacy .NET claim types
// for historical WS-Fed compatibility. Disabling that keeps claim types exactly as they appear
// in the token ("oid", "tid", "scp", ...). This decision is made once, globally, here — every
// piece of code reading claims (this wiring, and the integration tests' test auth handlers) must
// agree on it, or you get the classic "tests green, production 403" bug from mismatched claim
// names.
builder.Services.Configure<JwtBearerOptions>(
    JwtBearerDefaults.AuthenticationScheme,
    options => options.MapInboundClaims = false);

// IdempotencyFilter (and any other consumer) needs a testable system clock — singleton
// is safe since SystemClock carries no state of its own.
builder.Services.AddSingleton<IClock, SystemClock>();

// Scoped (not singleton) in case it ever needs scoped dependencies later; a stateless class
// registered as scoped costs nothing.
builder.Services.AddScoped<TenantSaveChangesInterceptor>();

// The ADR-017 tenant context. Scoped, not singleton/transient: it must live exactly as long as
// the request scope that TenantContextResolutionMiddleware populates it for, and every
// resolution within that scope (including inside IdentityDbContext) must see the same instance.
builder.Services.AddScoped<HttpContextTenantContext>();
builder.Services.AddScoped<ITenantContext>(sp => sp.GetRequiredService<HttpContextTenantContext>());

// AddDbContext (scoped), not AddDbContextPool: IdentityDbContext.CurrentTenantId is set once per
// request (by the tenant context resolution middleware) and must not leak across requests via a
// pooled instance.
builder.Services.AddDbContext<IdentityDbContext>((sp, options) =>
{
    var interceptor = sp.GetRequiredService<TenantSaveChangesInterceptor>();
    var connectionString = builder.Configuration.GetConnectionString("IdentityDb");

    options
        .UseSqlServer(connectionString)
        .AddInterceptors(interceptor);
});

// The first repository port in the codebase — Application depends on IUserRepository,
// never on IdentityDbContext directly; this is the Infrastructure-side implementation, wired
// scoped to match IdentityDbContext's own scoped lifetime.
builder.Services.AddScoped<IUserRepository, UserRepository>();
builder.Services.AddScoped<EnsureUserProvisioned>();

// The one sanctioned cross-tenant bypass in the codebase (ADR-017) — scoped to match
// IdentityDbContext's own scoped lifetime, following the established registration pattern.
builder.Services.AddScoped<IMembershipDirectory, MembershipDirectory>();

// The second repository port in the codebase, following the established minimal per-use-case
// pattern — scoped to match IdentityDbContext's own scoped lifetime.
builder.Services.AddScoped<ICreateTenantRepository, CreateTenantRepository>();
builder.Services.AddScoped<CreateTenant>();

// The third repository port in the codebase — one shared port for the read/rename-shaped
// GetTenant/RenameTenant/ListTenants use cases, scoped to match IdentityDbContext's own scoped
// lifetime.
builder.Services.AddScoped<ITenantRepository, TenantRepository>();
builder.Services.AddScoped<GetTenant>();
builder.Services.AddScoped<RenameTenant>();
builder.Services.AddScoped<ListTenants>();

// The fourth repository port in the codebase — landed ahead of the RemoveMember/role-change
// use cases that will consume it, following the established minimal per-use-case pattern. Guards
// the last-administrator invariant against genuine concurrent removals via a tenant row lock (see
// MembershipRepository's remarks) — scoped to match IdentityDbContext's own scoped lifetime.
builder.Services.AddScoped<IMembershipRepository, MembershipRepository>();

// The audit writer port — used by domain use cases to record audit entries during entity
// change tracking, scoped to match IdentityDbContext's own scoped lifetime.
builder.Services.AddScoped<IAuditWriter, AuditWriter>();

// The ListMembers/RemoveMember use cases, wired here per the same deferral note as the
// repository port above (same "port lands ahead of its use case's DI registration" shape as
// InviteMember et al. below).
builder.Services.AddScoped<Identity.Application.Members.ListMembers>();
builder.Services.AddScoped<Identity.Application.Members.RemoveMember>();
builder.Services.AddScoped<Identity.Application.Members.ChangeMemberRole>();

// The fifth repository port in the codebase, wired here per the same deferral note as above —
// one shared port for the invite/accept/list/revoke invitation use cases, scoped to match
// IdentityDbContext's own scoped lifetime.
builder.Services.AddScoped<IInvitationRepository, InvitationRepository>();

// Assumption 8's dev-time invitation delivery sink — a stateless structured-logging
// wrapper, so singleton is safe (no per-request state, unlike the scoped registrations above).
builder.Services.AddSingleton<
    Identity.Application.Invitations.IInvitationDeliverySink,
    Identity.Infrastructure.Notifications.LoggingInvitationDeliverySink>();

builder.Services.AddScoped<Identity.Application.Invitations.InviteMember>();
builder.Services.AddScoped<Identity.Application.Invitations.AcceptInvitation>();
builder.Services.AddScoped<Identity.Application.Invitations.ListInvitations>();
builder.Services.AddScoped<Identity.Application.Invitations.RevokeInvitation>();

// The "TenantAdministrator" policy mechanism, evaluated against the membership resolved by
// TenantContextResolutionMiddleware (ADR-017 step 5) via ITenantContext.Role, never against
// a token claim. Registered here only — no endpoint applies this policy yet; wiring it onto real
// routes (e.g. the role-change/removal endpoints) is deferred until those routes exist.
builder.Services.AddAuthorization(options =>
{
    // Every endpoint that calls RequireAuthorization() without naming a policy gets this one
    // (ADR-022): scope access_as_user for users, role Tenancy.Automation.Member for the one
    // named automation identity, nothing else.
    options.DefaultPolicy = CallerAuthorizationPolicy.Build();

    options.AddPolicy(
        "TenantAdministrator",
        policy => policy.Requirements.Add(new AdministratorOnlyRequirement()));
});
builder.Services.AddScoped<IAuthorizationHandler, AdministratorOnlyAuthorizationHandler>();

// The /health/ready dependency check. Uses the connectionStringFactory overload
// (resolved per check execution, from the request-scoped IServiceProvider health checks run
// under) rather than a string captured once at startup, so this always reuses whatever
// connection string IdentityDbContext is actually configured with right now — including
// Identity.IntegrationTests' ApiFactory, which repoints IdentityDbContext's DbContextOptions at its
// test container after Program.cs's own registration above runs. Capturing
// builder.Configuration.GetConnectionString("IdentityDb") once here would silently go stale in
// that scenario (and in general, if the connection string could ever change post-startup).
// Tagged "ready" so /health/live's route mapping can select "run no checks at all" via a
// predicate that simply never matches this tag, while /health/ready's mapping selects it via a
// predicate that does.
// The third state ("not-yet-ready"): a singleton flag flipped once this process's own
// startup work (the dev-time migration below) has finished, and a health check that reports it.
// Also tagged "ready" so it participates in /health/ready alongside the SQL Server check above —
// while either is unhealthy, /health/ready as a whole is unhealthy.
builder.Services.AddSingleton<StartupState>();

builder.Services.AddHealthChecks()
    .AddSqlServer(
        sp => sp.GetRequiredService<IdentityDbContext>().Database.GetConnectionString()!,
        name: "sqlserver",
        tags: ["ready"])
    .AddCheck<StartupHealthCheck>("startup", tags: ["ready"]);

// Graceful shutdown budget (FR-007, research.md R4): a documented value in code rather than
// the framework's inherited 30s default nobody chose. This is the drain window only — up to
// ~5s per OpenTelemetry provider (traces/metrics/logs) can run *after* this expires if the
// Collector is unreachable, which is why the container's stop_grace_period in compose.yaml is
// set well above the sum of the two, not just this number.
builder.Services.Configure<HostOptions>(options =>
    options.ShutdownTimeout = TimeSpan.FromSeconds(15));

var app = builder.Build();

// The draining half of the readiness lifecycle: ApplicationStopping fires as soon as
// SIGTERM is received, before Kestrel finishes draining in-flight requests, so
// /health/ready flips to "shutting down" immediately rather than only once the process is
// already exiting.
app.Lifetime.ApplicationStopping.Register(() =>
    app.Services.GetRequiredService<StartupState>().MarkStopping());

// Configure the HTTP request pipeline.
if (app.Environment.IsDevelopment())
{
    app.MapOpenApi();
}

// Development-only auto-migrate: keeps local dev schema current without a manual `dotnet ef
// database update` step. Deliberately excluded from staging/production, where applying
// migrations is a separate, reviewed deployment step (out of scope for this slice).
//
// Never replace this with EnsureCreated(): it creates the schema straight from the current
// model with no row in the migrations history table, so any later Migrate() call against that
// database fails (EF Core has no baseline to reconcile against). Always use MigrateAsync().
if (app.Environment.IsDevelopment())
{
    // Edge case 3 (a termination signal arriving before readiness): this whole block runs
    // before app.Run(), i.e. before ConsoleLifetime installs its own SIGTERM handling —
    // empirically confirmed (docker stop against a container stuck retrying a stopped
    // database mid-migration) to hard-kill the process with exit 143 and no graceful path at
    // all, because app.Lifetime.ApplicationStopping is never signalled this early: nothing
    // is listening for the signal yet at the OS level. PosixSignalRegistration is a
    // process-wide registration independent of the host's own lifecycle, so it is active
    // immediately and suppresses the OS's default kill-on-SIGTERM disposition for as long as
    // it is held — exactly the window this migration call needs covered.
    using var earlyShutdown = new CancellationTokenSource();
    using var earlyShutdownSignal = System.Runtime.InteropServices.PosixSignalRegistration.Create(
        System.Runtime.InteropServices.PosixSignal.SIGTERM,
        context =>
        {
            // PosixSignalContext.Cancel defaults to false — the runtime's default
            // terminate-the-process action still runs after this handler returns unless this
            // is set explicitly. Without it, this whole registration is a no-op that races
            // its own cancellation against an unconditional kill (confirmed empirically: the
            // token was cancelled, but the process still died with exit 143 every time).
            context.Cancel = true;
            earlyShutdown.Cancel();
        });

    using var scope = app.Services.CreateScope();
    var db = scope.ServiceProvider.GetRequiredService<IdentityDbContext>();

    try
    {
        await db.Database.MigrateAsync(earlyShutdown.Token);
    }
    catch (OperationCanceledException) when (earlyShutdown.IsCancellationRequested)
    {
        // A signal arrived before startup finished. Exit now, without ever calling
        // MarkReady() or app.Run() — the container must never advertise readiness or accept
        // a connection in this path. DisposeAsync (rather than just returning) still runs
        // registered services' shutdown/dispose logic, including OpenTelemetry's provider
        // flush, so this remains a clean exit rather than an abandoned one.
        await app.DisposeAsync();
        return;
    }
}

// The "not-yet-ready" state ends here: all startup work above (dev-time migration
// included) has finished, so /health/ready's "startup" check can start reporting Healthy.
app.Services.GetRequiredService<StartupState>().MarkReady();

// The log-correlation half of request tracing: pushes the request's TraceId into an ILogger scope for
// the whole pipeline. Registered before UseExceptionHandler() so log lines emitted while
// producing an error response are correlated too, not just the happy path.
app.UseTraceCorrelationLogging();

// Registered before UseAuthentication()/UseAuthorization() (and everything else) so it catches
// unhandled exceptions thrown anywhere downstream in the pipeline, including auth/authz.
app.UseExceptionHandler();

// Gated, not deleted (research.md R5): a container listens on plain HTTP only, with TLS
// terminated upstream from S6 onward, and no HTTPS port ever discoverable. Calling this
// unconditionally is a silent no-op today, but a booby trap if an HTTPS port ever *becomes*
// discoverable (an inherited ASPNETCORE_HTTPS_PORT) — every request, including
// /health/ready, would start receiving a 307 instead of being served. compose.yaml sets
// Https__RedirectionEnabled=false explicitly; the dotnet run / User Secrets workflow keeps
// the default of true, where a real HTTPS port exists.
if (app.Configuration.GetValue("Https:RedirectionEnabled", true))
{
    app.UseHttpsRedirection();
}

// IdempotencyFilter (an IEndpointFilter) needs to re-read the raw request body after
// model binding has already consumed it, to compute its request-hash. Model binding for minimal
// API JSON parameters reads via HttpRequest.BodyReader (a PipeReader), not HttpRequest.Body (the
// Stream) directly; calling EnableBuffering() only once binding is already underway (i.e. from
// inside the filter itself, the first time anything tries to read the body) is too late for that
// PipeReader-based read to be replayable. Enabling buffering here, as the very first thing that
// touches the request, ensures whichever reader gets to the body first (the JSON binder or the
// filter) leaves it seekable for the other.
app.Use((context, next) =>
{
    context.Request.EnableBuffering();
    return next(context);
});

app.UseAuthentication();

// The user-identity enrichment half of request tracing: tags Activity.Current and pushes a log scope
// for every authenticated request, regardless of whether the endpoint ever resolves a tenant
// context (the three ADR-017-exempt operations included). Registered after UseAuthentication()
// so context.User is populated, and before UseAuthorization() so the enrichment covers 403s too.
app.UseUserIdentityEnrichment();

app.UseAuthorization();

// Liveness/readiness probes. Mapped outside any authorization requirement (and
// explicitly .AllowAnonymous()'d) since infrastructure probes (load balancers, orchestrators)
// have no credentials to present — see contracts/health-endpoints.md. /health/live's predicate
// matches no registered check (not even the "ready"-tagged SQL Server one) so liveness never
// depends on SQL Server; /health/ready's predicate selects exactly the "ready"-tagged check(s).
// Both use HealthCheckResponseWriter for the response body; ResultStatusCodes' own default
// already maps HealthStatus.Unhealthy to 503, so /health/ready gets that for free.
app.MapHealthChecks("/health/live", new HealthCheckOptions
{
    Predicate = _ => false,
    ResponseWriter = HealthCheckResponseWriter.WriteResponse,
}).AllowAnonymous();

app.MapHealthChecks("/health/ready", new HealthCheckOptions
{
    Predicate = check => check.Tags.Contains("ready"),
    ResponseWriter = HealthCheckResponseWriter.WriteResponse,
}).AllowAnonymous();

// The four /tenants endpoints.
app.MapTenantEndpoints();

// The invitation endpoints.
app.MapInvitationEndpoints();

// The member endpoints.
app.MapMemberEndpoints();

app.Run();

/// <summary>
/// The implicit top-level-statement <c>Program</c> class is <c>internal</c> by default, which
/// hides it from other assemblies. Identity.IntegrationTests' <c>ApiFactory</c> needs
/// <c>WebApplicationFactory&lt;Program&gt;</c> to reference this exact type, so it is declared
/// <c>public partial</c> here — combined with the <c>InternalsVisibleTo</c> below, which is the
/// belt-and-suspenders option since some tooling still expects it even when the type itself is
/// public.
/// </summary>
public partial class Program
{
}
