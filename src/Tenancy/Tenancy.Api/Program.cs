using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.AspNetCore.Authorization;
using Microsoft.EntityFrameworkCore;
using Microsoft.Identity.Web;
using Tenancy.Api.Authorization;
using Tenancy.Api.Configuration;
using Tenancy.Api.Endpoints;
using Tenancy.Api.ErrorHandling;
using Tenancy.Api.Middleware;
using Tenancy.Application.Abstractions;
using Tenancy.Application.Tenants;
using Tenancy.Application.Users;
using Tenancy.Domain.Abstractions;
using Tenancy.Infrastructure.Observability;
using Tenancy.Infrastructure.Persistence;
using Tenancy.Infrastructure.Persistence.Audited;
using Tenancy.Infrastructure.Persistence.Interceptors;
using Tenancy.Infrastructure.Security;

var builder = WebApplication.CreateBuilder(args);

// FR-016/Assumption 7's revocation-staleness trade-off, made an operationally checked
// expectation rather than a design note nobody will find later (see RevocationWindowTests,
// T069, and TokenLifetimeValidation's remarks): this API performs no per-request token
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

builder.Services.AddTenancyObservability(builder.Configuration);

// RFC 9457 global error handling (FR-022): AddExceptionHandler alone is not sufficient —
// AddProblemDetails() supplies the ProblemDetails-writing infrastructure that the exception
// handler middleware (registered below via UseExceptionHandler()) relies on, and
// ProblemDetailsHandler is where the actual "never leak exception.Message/StackTrace/type"
// contract is enforced. All three pieces (AddExceptionHandler + AddProblemDetails +
// UseExceptionHandler) are required together for this to take effect.
builder.Services.AddExceptionHandler<ProblemDetailsHandler>();
builder.Services.AddProblemDetails();

// Entra ID (Azure AD) bearer-token authentication. T033 populates the "AzureAd" configuration
// section (tenant/client IDs, etc.) via User Secrets; this task only wires the scheme.
builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
    .AddMicrosoftIdentityWebApi(builder.Configuration.GetSection("AzureAd"));

// By default, ASP.NET Core's JWT handler remaps standard OIDC claim names (e.g. "oid" ->
// "http://schemas.microsoft.com/identity/claims/objectidentifier") into legacy .NET claim types
// for historical WS-Fed compatibility. Disabling that keeps claim types exactly as they appear
// in the token ("oid", "tid", "scp", ...). This decision is made once, globally, here — every
// piece of code reading claims (this wiring, and T040/T041's test auth handlers) must agree on
// it, or you get the classic "tests green, production 403" bug from mismatched claim names.
builder.Services.Configure<JwtBearerOptions>(
    JwtBearerDefaults.AuthenticationScheme,
    options => options.MapInboundClaims = false);

// T056's IdempotencyFilter (and any other consumer) needs a testable system clock — singleton
// is safe since SystemClock carries no state of its own.
builder.Services.AddSingleton<IClock, SystemClock>();

// Scoped (not singleton) in case it ever needs scoped dependencies later; a stateless class
// registered as scoped costs nothing.
builder.Services.AddScoped<TenantSaveChangesInterceptor>();

// The ADR-017 tenant context. Scoped, not singleton/transient: it must live exactly as long as
// the request scope that TenantContextResolutionMiddleware (T035) populates it for, and every
// resolution within that scope (including inside TenancyDbContext) must see the same instance.
builder.Services.AddScoped<HttpContextTenantContext>();
builder.Services.AddScoped<ITenantContext>(sp => sp.GetRequiredService<HttpContextTenantContext>());

// AddDbContext (scoped), not AddDbContextPool: TenancyDbContext.CurrentTenantId is set once per
// request (T035's middleware) and must not leak across requests via a pooled instance.
builder.Services.AddDbContext<TenancyDbContext>((sp, options) =>
{
    var interceptor = sp.GetRequiredService<TenantSaveChangesInterceptor>();
    var connectionString = builder.Configuration.GetConnectionString("TenancyDb");

    options
        .UseSqlServer(connectionString)
        .AddInterceptors(interceptor);
});

// The first repository port in the codebase (T036) — Application depends on IUserRepository,
// never on TenancyDbContext directly; this is the Infrastructure-side implementation, wired
// scoped to match TenancyDbContext's own scoped lifetime.
builder.Services.AddScoped<IUserRepository, UserRepository>();
builder.Services.AddScoped<EnsureUserProvisioned>();

// The one sanctioned cross-tenant bypass in the codebase (T037, ADR-017) — scoped to match
// TenancyDbContext's own scoped lifetime, following T036's registration pattern.
builder.Services.AddScoped<IMembershipDirectory, MembershipDirectory>();

// The second repository port in the codebase (T054), following T036's minimal per-use-case
// pattern — scoped to match TenancyDbContext's own scoped lifetime.
builder.Services.AddScoped<ICreateTenantRepository, CreateTenantRepository>();
builder.Services.AddScoped<CreateTenant>();

// The third repository port in the codebase (T055) — one shared port for the read/rename-shaped
// GetTenant/RenameTenant/ListTenants use cases, scoped to match TenancyDbContext's own scoped
// lifetime.
builder.Services.AddScoped<ITenantRepository, TenantRepository>();
builder.Services.AddScoped<GetTenant>();
builder.Services.AddScoped<RenameTenant>();
builder.Services.AddScoped<ListTenants>();

// The fourth repository port in the codebase (T075) — landed ahead of the RemoveMember/role-change
// use cases (T076) that will consume it, following T036's minimal per-use-case pattern. Guards the
// last-administrator invariant against genuine concurrent removals via a tenant row lock (see
// MembershipRepository's remarks) — scoped to match TenancyDbContext's own scoped lifetime.
builder.Services.AddScoped<IMembershipRepository, MembershipRepository>();

// The audit writer port — used by domain use cases to record audit entries during entity
// change tracking, scoped to match TenancyDbContext's own scoped lifetime.
builder.Services.AddScoped<IAuditWriter, AuditWriter>();

// T076's ListMembers/RemoveMember use cases, wired here at T079 per that task's own deferral note
// (same "port lands ahead of its use case's DI registration" shape as InviteMember et al. above).
builder.Services.AddScoped<Tenancy.Application.Members.ListMembers>();
builder.Services.AddScoped<Tenancy.Application.Members.RemoveMember>();
builder.Services.AddScoped<Tenancy.Application.Members.ChangeMemberRole>();

// The fifth repository port in the codebase (T071-T073, wired here at T078 per that task's own
// deferral note) — one shared port for the invite/accept/list/revoke invitation use cases,
// scoped to match TenancyDbContext's own scoped lifetime.
builder.Services.AddScoped<IInvitationRepository, InvitationRepository>();

// T080/Assumption 8's dev-time invitation delivery sink — a stateless structured-logging
// wrapper, so singleton is safe (no per-request state, unlike the scoped registrations above).
builder.Services.AddSingleton<
    Tenancy.Application.Invitations.IInvitationDeliverySink,
    Tenancy.Infrastructure.Notifications.LoggingInvitationDeliverySink>();

builder.Services.AddScoped<Tenancy.Application.Invitations.InviteMember>();
builder.Services.AddScoped<Tenancy.Application.Invitations.AcceptInvitation>();
builder.Services.AddScoped<Tenancy.Application.Invitations.ListInvitations>();
builder.Services.AddScoped<Tenancy.Application.Invitations.RevokeInvitation>();

// T085: the "TenantAdministrator" policy mechanism, evaluated against the membership resolved by
// TenantContextResolutionMiddleware (T035/ADR-017 step 5) via ITenantContext.Role, never against
// a token claim. Registered here only — no endpoint applies this policy yet; wiring it onto real
// routes (e.g. the role-change/removal endpoints) is T088's job, once those routes exist.
builder.Services.AddAuthorization(options =>
{
    options.AddPolicy(
        "TenantAdministrator",
        policy => policy.Requirements.Add(new AdministratorOnlyRequirement()));
});
builder.Services.AddScoped<IAuthorizationHandler, AdministratorOnlyAuthorizationHandler>();

var app = builder.Build();

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
    using var scope = app.Services.CreateScope();
    var db = scope.ServiceProvider.GetRequiredService<TenancyDbContext>();
    await db.Database.MigrateAsync();
}

// FR-001's log-correlation half (T021): pushes the request's TraceId into an ILogger scope for
// the whole pipeline. Registered before UseExceptionHandler() so log lines emitted while
// producing an error response are correlated too, not just the happy path.
app.UseTraceCorrelationLogging();

// Registered before UseAuthentication()/UseAuthorization() (and everything else) so it catches
// unhandled exceptions thrown anywhere downstream in the pipeline, including auth/authz.
app.UseExceptionHandler();

app.UseHttpsRedirection();

// T056's IdempotencyFilter (an IEndpointFilter) needs to re-read the raw request body after
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

// FR-004's user-identity enrichment half (T022): tags Activity.Current and pushes a log scope
// for every authenticated request, regardless of whether the endpoint ever resolves a tenant
// context (the three ADR-017-exempt operations included). Registered after UseAuthentication()
// so context.User is populated, and before UseAuthorization() so the enrichment covers 403s too.
app.UseUserIdentityEnrichment();

app.UseAuthorization();

// T058: the four /tenants endpoints wiring together T032-T057.
app.MapTenantEndpoints();

// T078: the invitation endpoints wiring together T071-T073.
app.MapInvitationEndpoints();

// T079: the member endpoints wiring together T075-T076.
app.MapMemberEndpoints();

app.Run();

/// <summary>
/// The implicit top-level-statement <c>Program</c> class is <c>internal</c> by default, which
/// hides it from other assemblies. Tenancy.IntegrationTests' <c>ApiFactory</c> (T042) needs
/// <c>WebApplicationFactory&lt;Program&gt;</c> to reference this exact type, so it is declared
/// <c>public partial</c> here — combined with the <c>InternalsVisibleTo</c> below, which is the
/// belt-and-suspenders option since some tooling still expects it even when the type itself is
/// public.
/// </summary>
public partial class Program
{
}
