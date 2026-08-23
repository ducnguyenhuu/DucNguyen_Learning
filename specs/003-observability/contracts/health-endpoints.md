# Contract: Health Check Endpoints

Two routes, both unauthenticated (health checks must be reachable by infrastructure
probes that have no credentials), both read-only, neither tenant-scoped.

## `GET /health/live`

Liveness — is the process itself running? No dependency check.

**Response 200 OK** (always, if the process can respond at all):
```json
{ "status": "Healthy" }
```

If this route does not respond, the process should be restarted — that is the
liveness contract by definition, not a response this endpoint itself produces.

## `GET /health/ready`

Readiness — is the process running AND are its dependencies (at minimum, SQL Server)
reachable? This is the route that reflects FR-008's three states.

**Response 200 OK** — healthy, all dependency checks passed:
```json
{
  "status": "Healthy",
  "checks": [
    { "name": "sqlserver", "status": "Healthy" }
  ]
}
```

**Response 503 Service Unavailable** — unhealthy, naming the failing dependency:
```json
{
  "status": "Unhealthy",
  "checks": [
    { "name": "sqlserver", "status": "Unhealthy", "description": "Could not reach the database" }
  ]
}
```

**Response 503 Service Unavailable** — not-yet-ready (startup incomplete, e.g.
migrations still running):
```json
{
  "status": "Unhealthy",
  "checks": [
    { "name": "sqlserver", "status": "Unhealthy", "description": "Startup not yet complete" }
  ]
}
```

The not-yet-ready and genuinely-unhealthy cases share the same HTTP status
(503) and JSON shape by design — an external caller (a load balancer, an
orchestrator) treats both identically ("don't route traffic here yet"). The
distinction between "still starting" and "broken" is for a human reading the
`description` field or correlating with `/health/live` (which reports `Healthy`
in the not-yet-ready case, since the process itself is up), not for automated
routing decisions.
