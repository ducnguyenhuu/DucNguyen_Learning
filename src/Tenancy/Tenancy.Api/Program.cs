using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.EntityFrameworkCore;
using Microsoft.Identity.Web;
using Tenancy.Api.ErrorHandling;
using Tenancy.Api.Middleware;
using Tenancy.Application.Abstractions;
using Tenancy.Application.Tenants;
using Tenancy.Application.Users;
using Tenancy.Infrastructure.Persistence;
using Tenancy.Infrastructure.Persistence.Audited;
using Tenancy.Infrastructure.Persistence.Interceptors;
using Tenancy.Infrastructure.Security;

var builder = WebApplication.CreateBuilder(args);

// Add services to the container.
// Learn more about configuring OpenAPI at https://aka.ms/aspnet/openapi
builder.Services.AddOpenApi();

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

// Registered before UseAuthentication()/UseAuthorization() (and everything else) so it catches
// unhandled exceptions thrown anywhere downstream in the pipeline, including auth/authz.
app.UseExceptionHandler();

app.UseHttpsRedirection();

app.UseAuthentication();
app.UseAuthorization();

var summaries = new[]
{
    "Freezing", "Bracing", "Chilly", "Cool", "Mild", "Warm", "Balmy", "Hot", "Sweltering", "Scorching"
};

app.MapGet("/weatherforecast", () =>
{
    var forecast =  Enumerable.Range(1, 5).Select(index =>
        new WeatherForecast
        (
            DateOnly.FromDateTime(DateTime.Now.AddDays(index)),
            Random.Shared.Next(-20, 55),
            summaries[Random.Shared.Next(summaries.Length)]
        ))
        .ToArray();
    return forecast;
})
.WithName("GetWeatherForecast");

app.Run();

record WeatherForecast(DateOnly Date, int TemperatureC, string? Summary)
{
    public int TemperatureF => 32 + (int)(TemperatureC / 0.5556);
}

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
