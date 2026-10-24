# syntax=docker/dockerfile:1
#
# Multi-stage build: SDK stage restores and publishes both the API and the health probe;
# the runtime stage is the chiseled ASP.NET Core base, which ships no shell, no package
# manager, and already sets USER $APP_UID (research.md R1). See
# specs/004-containerization/contracts/container-image.md for the full image contract.

FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /src

# Copy only what `dotnet restore` needs first, so dependency restore is cached
# independently of source changes.
COPY global.json Directory.Build.props Directory.Packages.props DeliveryIntelligence.slnx ./
COPY src/Identity/Identity.Api/Identity.Api.csproj src/Identity/Identity.Api/
COPY src/Identity/Identity.Application/Identity.Application.csproj src/Identity/Identity.Application/
COPY src/Identity/Identity.Domain/Identity.Domain.csproj src/Identity/Identity.Domain/
COPY src/Identity/Identity.Infrastructure/Identity.Infrastructure.csproj src/Identity/Identity.Infrastructure/
COPY src/Identity/Identity.HealthProbe/Identity.HealthProbe.csproj src/Identity/Identity.HealthProbe/
RUN dotnet restore src/Identity/Identity.Api/Identity.Api.csproj \
    && dotnet restore src/Identity/Identity.HealthProbe/Identity.HealthProbe.csproj

COPY src/ src/

RUN dotnet publish src/Identity/Identity.Api/Identity.Api.csproj \
        -c Release -o /app/publish --no-restore \
    && dotnet publish src/Identity/Identity.HealthProbe/Identity.HealthProbe.csproj \
        -c Release -o /app/probe --no-restore

FROM mcr.microsoft.com/dotnet/aspnet:10.0-noble-chiseled-extra AS runtime
WORKDIR /app

# -extra, not plain chiseled (research.md R1, corrected): Microsoft.Data.SqlClient throws
# System.NotSupportedException ("Globalization Invariant Mode is not supported") on connection
# open under Invariant Globalization — a runtime dependency on ICU that has nothing to do with
# this service's own code ever calling CultureInfo/TimeZoneInfo. Plain chiseled forces
# invariant mode unconditionally, which made this untestable until an actual container ran
# against real SQL Server; -extra restores ICU/tzdata (+14.8 MB compressed) — exactly the
# fallback research.md flagged if a culture-dependent hazard ever surfaced, just not the one
# predicted.
ENV DOTNET_GENERATE_ASPNET_CERTIFICATE=false

# Already the chiseled base's default; set explicitly so a future base-image change cannot
# silently reintroduce root (FR-002, contracts/container-image.md).
USER $APP_UID

COPY --from=build /app/publish ./
COPY --from=build /app/probe ./probe/

# Exec form only: shell form would make /bin/sh PID 1, which does not forward SIGTERM, and
# a chiseled image has no /bin/sh anyway (research.md R4).
ENTRYPOINT ["dotnet", "Identity.Api.dll"]

# Exec form, invoking the health probe against the existing readiness surface — a chiseled
# image has no shell and no curl, so neither a shell-form HEALTHCHECK nor a curl-based
# Compose healthcheck is possible (research.md R1, contracts/container-image.md).
HEALTHCHECK --interval=10s --timeout=3s --start-period=30s --retries=3 \
    CMD ["dotnet", "/app/probe/Identity.HealthProbe.dll", "http://localhost:8080/health/ready"]
