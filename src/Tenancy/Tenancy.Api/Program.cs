using Microsoft.EntityFrameworkCore;
using Tenancy.Infrastructure.Persistence;
using Tenancy.Infrastructure.Persistence.Interceptors;

var builder = WebApplication.CreateBuilder(args);

// Add services to the container.
// Learn more about configuring OpenAPI at https://aka.ms/aspnet/openapi
builder.Services.AddOpenApi();

// Scoped (not singleton) in case it ever needs scoped dependencies later; a stateless class
// registered as scoped costs nothing.
builder.Services.AddScoped<TenantSaveChangesInterceptor>();

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

app.UseHttpsRedirection();

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
