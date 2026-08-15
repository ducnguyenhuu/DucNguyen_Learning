# Tenancy migrations

## Model/migration drift check

There is no CI pipeline in this repo yet (checked: no `.github/workflows/` directory as of
T031). Until one exists, run this command manually before merging any change that touches
`TenancyDbContext` or its entities, and again once CI is introduced for this service:

```sh
dotnet ef migrations has-pending-model-changes \
  --project src/Tenancy/Tenancy.Infrastructure \
  --startup-project src/Tenancy/Tenancy.Api
```

It fails (non-zero exit) if the current model has changes not captured by an existing
migration under this folder — i.e. you changed an entity but forgot to run
`dotnet ef migrations add`. Catching this here is far cheaper than discovering schema drift
at `Migrate()` time in a running environment.

## Never use `EnsureCreated()`

`EnsureCreated()` builds the schema directly from the current model and skips the
`__EFMigrationsHistory` table entirely. A database created this way has no migration
history, so any later `Database.Migrate()` call against it fails — EF Core has nothing to
reconcile "no migrations applied" against "schema already matches migration N". This
applies everywhere in this project, including test fixtures (e.g. the Testcontainers
fixture in T039): apply migrations via `Migrate()`/`MigrateAsync()`, never `EnsureCreated()`.
