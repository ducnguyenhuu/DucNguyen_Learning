# ADR-011: OpenTelemetry as the instrumentation standard

**Status**: Accepted
**Date**: 2026-08-08
**Deciders**: Project owner
**Relates to**: Constitution → Principle VI · `idea.md` §20, §21, §44 item 6 · roadmap S4
**Refined by**: [ADR-018](ADR-018-new-relic-telemetry-backend.md) (2026-08-09) — the **backend**
is now New Relic, with Application Insights as an optional secondary. The instrumentation
decision below is unchanged and remains load-bearing.

## Context

`idea.md` §20 sets a specific and demanding requirement: a single user action crossing
Frontend → API → Delivery Service → Service Bus → AI Agent → AI Search → LLM must be
understandable as **one logical transaction**. That is a distributed tracing
requirement, and it spans HTTP, asynchronous messaging, and external AI calls.

Principle VI raises the bar further: a failure must be diagnosable from telemetry
alone, without local reproduction. That is only achievable if instrumentation is
consistent across every service and every boundary — inconsistent instrumentation
produces traces that break exactly where the interesting failures happen.

There is also a vendor question. ADR-001 commits to Azure, which supplies Application
Insights and its own SDK. Using it directly would be the path of least resistance.

## Decision

We use **OpenTelemetry** as the instrumentation API and SDK for all traces, metrics,
and logs, across every service.

~~Azure Monitor / Application Insights is the **backend**~~, reached via the OpenTelemetry
exporter — not via a vendor SDK.

> **Amended 2026-08-09 by [ADR-018](ADR-018-new-relic-telemetry-backend.md):** the default
> backend is **New Relic** over OTLP; Azure Monitor / Application Insights is an optional
> secondary exporter. The rule that matters here is unchanged — the backend is reached through
> the OpenTelemetry exporter, **never** through a vendor SDK or agent. This is the change this
> ADR's *Revisit When* anticipated: the exporter is repointed, the code is not rewritten.

Requirements that follow:

- **A correlation identifier is generated at the entry point and propagated across
  every boundary**, including through Service Bus messages (roadmap S8). W3C Trace
  Context is the propagation format.
- **Traces are enriched with tenant and user identity** (Principle IV, VI), and never
  with secrets or unnecessary personal data (Principle XI).
- **AI invocations record model, tokens, cost, latency, and outcome** as span
  attributes (Principle VI, ADR-009).
- Instrumentation is added as part of the work it instruments, not as a later pass.

## Consequences

### Positive

- Vendor-neutral: the backend can change without re-instrumenting. Given that AI
  observability tooling is evolving quickly, this optionality has real near-term value.
- Automatic instrumentation for ASP.NET Core, HttpClient, EF Core, and Azure SDKs
  covers most of the trace surface without hand-written spans.
- One instrumentation model for HTTP and messaging, which is what makes the
  unbroken trace across Service Bus in `idea.md` §20 achievable rather than aspirational.
- Aligns with `idea.md` §52's research interest in observability as a practice rather
  than as a vendor product.

### Negative

- **More configuration than the Application Insights SDK**, which would have been
  nearly turnkey on Azure. Exporter setup, resource attributes, and sampling all
  require explicit decisions.
- Some Application Insights features — Live Metrics, certain Profiler and Snapshot
  Debugger capabilities — are degraded or unavailable through the OTel exporter.
- The .NET OTel logging story has been less settled than tracing and metrics;
  expect some churn across versions.
- Cardinality discipline is now the team's problem. Tenant identity on every span is
  useful and also a cost multiplier in Log Analytics if applied carelessly.

### Neutral / accepted trade-offs

- Sampling will be needed eventually. It is deliberately not configured in Horizon 1,
  where volume is negligible and full traces are more valuable than cost savings.
- Local development uses a local collector or the .NET Aspire dashboard rather than
  Application Insights, so S4 is verifiable without Azure — a requirement created by
  ADR-007's decision to defer Azure to S6.

## Alternatives Considered

### Application Insights SDK directly

Least configuration, deepest Azure integration, best out-of-box experience on the
platform we are already committed to. Rejected on two grounds: it couples
instrumentation to a vendor at a layer that touches every file in the codebase, which
is the most expensive place to be coupled; and the AI observability tooling landscape
is moving fast enough that backend optionality is worth the configuration cost.

### Serilog plus a separate metrics library

Excellent structured logging, familiar in .NET. Rejected because it addresses logging
only. Distributed tracing across Service Bus — the actual hard requirement in §20 —
would still need OpenTelemetry or a bespoke solution, leaving two instrumentation
models to reconcile.

### Vendor APM agent (Datadog, New Relic, Honeycomb agent)

Strong tooling, minimal instrumentation effort. Rejected for Horizon 1 on cost and on
coupling. All three accept OTel data anyway, so this ADR does not preclude adopting
one as a backend later — which is precisely the optionality being bought.

> **Outcome (2026-08-09):** this is exactly what happened, and the distinction held.
> [ADR-018](ADR-018-new-relic-telemetry-backend.md) adopts New Relic as the OTLP **backend**
> while the **agent** remains rejected for the reason stated here. The optionality was real:
> repointing the backend required no change to any instrumentation, plan, or data model.

## Revisit When

- ~~Application Insights proves inadequate for AI-specific observability~~ — the backend
  question is now ADR-018's. AI-specific observability over OTLP remains the open risk, to be
  re-verified before S13.
- ~~Log Analytics cost~~ — ingest cost is now New Relic's 100 GB/month free tier, which fails
  hard rather than billing over. Sampling therefore moves *into* S4 rather than waiting for a
  cost signal (ADR-018).
- The .NET OTel logging API changes materially.

## Compliance

- **Roadmap S4 proof:** one tenant operation produces a single correlated trace from
  entry through to the database.
- **Roadmap S8 proof:** a distributed trace spans HTTP entry → publish → Service Bus →
  subscriber → database without breaking.
- **Gate 1:** an induced failure is diagnosed from telemetry alone in under 10 minutes.
- **Principle VI, spec 001 FR-025:** no secret and no unnecessary personal data appears
  in telemetry.

**Known weakness:** "is this code instrumented?" is not automatically enforceable in
any straightforward way. The practical gate is the Gate 1 diagnosis exercise — if a
failure cannot be diagnosed from telemetry, instrumentation is inadequate by
definition. That is a real test but a coarse one, applied late.
