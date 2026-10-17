# ADR-018: New Relic as the default telemetry backend

**Status**: Accepted
**Date**: 2026-08-09
**Deciders**: Project owner
**Relates to**: Constitution → Principle VI · ADR-011 (refines) · ADR-001 (exception granted under) · `idea.md` §17, §20 · roadmap S4, S6

## Context

ADR-011 chose OpenTelemetry as the instrumentation API and named **Azure Monitor /
Application Insights** as the backend, reached through the OTLP exporter rather than the
Application Insights SDK. ADR-001 named the same thing as part of its Azure-first decision,
and requires that "adopting a non-Azure service requires its own ADR stating why the Azure
equivalent is insufficient." This is that ADR.

Two things make the change cheap and worth making now, before S4 exists:

**ADR-011 anticipated exactly this.** Its rejected-alternatives section considered a vendor
APM agent and concluded: *"All three accept OTel data anyway, so this ADR does not preclude
adopting one as a backend later — which is precisely the optionality being bought."* Its
*Revisit When* adds that the correct response is that *"the exporter is repointed rather than
the code rewritten."*

**The distinction that keeps ADR-011 intact** is agent versus backend. ADR-011 rejected the
vendor *agent* — proprietary instrumentation touching every file, which is the expensive place
to be coupled. It did not reject the vendor as an OTLP *destination*. This ADR changes only
the destination.

## Decision

**New Relic is the default telemetry backend**, receiving OpenTelemetry data over OTLP.

- **Instrumentation remains pure OpenTelemetry.** No New Relic APM agent, no vendor SDK, no
  vendor-specific attributes in application code. ADR-011's decision stands unchanged.
- **Azure Monitor / Application Insights becomes an optional secondary exporter**, not the
  default. It is a connector that can be switched on, not a dependency.
- **Fan-out happens in the OpenTelemetry Collector**, not in application code. Services export
  OTLP once, to the collector; the collector decides where it goes.

### Why the collector, and not two in-process exporters

This is forced by a technical incompatibility rather than chosen on taste:

**New Relic is a delta-metrics system; Azure Monitor expects cumulative.** In-process there is
one `MeterProvider` whose temporality is a single global preference, so it cannot serve both.
In the collector, the application exports cumulative once and a `cumulativetodelta` processor
runs on the New Relic branch only.

Three lesser reasons point the same way: `UseOtlpExporter()` may only be called once and
cannot be combined with per-signal `AddOtlpExporter()`; toggling the secondary backend becomes
a config change rather than an application redeploy; and both credentials live in one egress
point alongside the sampling and drop rules.

### Required configuration

Non-obvious settings, each of which is wrong by default:

| Setting | Value | Why |
|---|---|---|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `https://otlp.nr-data.net` (US) or `https://otlp.eu01.nr-data.net` (EU) | Region choice is a data-residency decision, not a performance one |
| `OTEL_EXPORTER_OTLP_HEADERS` | `api-key=<INGEST_LICENSE_KEY>` | The **ingest licence key**, not a User API key. A secret — Key Vault from S6, User Secrets before that |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | `http/protobuf` | New Relic recommends it over gRPC as more robust with no measured performance cost |
| `OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE` | `delta` | **The .NET SDK defaults to cumulative.** Leaving this unset means server-side conversion, extra latency, and reset-detection risk |
| `OTEL_ATTRIBUTE_VALUE_LENGTH_LIMIT` | `4095` | Matches New Relic's limit, so truncation happens locally and visibly rather than as a silent server-side mangle |
| Histograms | base-2 exponential, via a View | Explicit-bucket histograms are converted by lossy linear interpolation |

Payload limit is **1 MB per request**, hard-rejected — batch sizes must be tuned, not left at
defaults.

### The tenant-annotation rule this creates

Principle VI requires telemetry annotated with tenant identity. New Relic's cardinality limits
apply **per metric name, per account, per UTC day** — and they apply to **metrics only**.

> **Tenant identity goes on spans and logs. It must NOT become a metric dimension.**

Spans and logs are events, priced by ingest volume, and high-cardinality attributes on them
are normal and queryable. A `tenant.id` dimension on a metric multiplies timeseries by tenant
count and will breach the cardinality limit as tenants grow. Where per-tenant metrics are
genuinely needed, use a bounded proxy — tenant tier or shard — not the identity.

This is a permanent design rule, not a tuning note, and it is the kind of thing that is very
cheap to get right now and expensive to unpick after dashboards depend on it.

## Consequences

### Positive

- **It converts ADR-011's central claim from an assertion into a demonstrated result.**
  ADR-011 bought backend optionality and paid configuration cost for it. Until the backend
  actually changes, "the backend can change without re-instrumenting" is untested. Repointing
  an exporter and having instrumentation survive unchanged is a real finding, and
  `idea.md` §52 treats observability as a practice to be researched rather than a vendor
  product to be bought. Evidence for this already exists: **this decision required no change
  to spec 001's plan, research, or data model** — the abstraction held.
- **S4 becomes verifiable against a real backend without Azure.** ADR-011 had to settle for a
  local collector or the Aspire dashboard in S4, because Application Insights requires a
  subscription. New Relic's free tier removes that compromise, so S4's proof — diagnosing an
  induced failure from telemetry alone — runs against the real thing two slices earlier than
  planned. This is a genuine improvement to the roadmap, not merely a lateral move.
- **Cost at this project's scale is effectively zero**: 100 GB/month ingest and one
  full-platform user, free perpetually. Paid overage is $0.40/GB, materially below Log
  Analytics' per-GB Analytics tier.
- Not tying observability to one cloud suits a platform whose own value proposition is
  intelligence *across* systems.

### Negative

- **The free tier fails hard, not softly.** Exceeding 100 GB in a month stops ingest *and
  revokes platform access* until the month rolls over or the account is upgraded. There is no
  surprise invoice, which is safer than Azure's model — but an accidental log flood costs
  observability for days. Sampling and collector-side drop rules are therefore not a later
  optimisation; they are part of S4.
- **A second vendor to operate**, with its own credential to rotate and its own outage
  surface, on a project that had deliberately consolidated on one provider (ADR-001).
- **The Azure Monitor path degrades to beta.** The collector's `azure_monitor` exporter is
  beta for all three signals, contrib-only, with two code owners — and **span events are off
  by default**, which silently drops .NET exception records. If Application Insights fidelity
  ever matters, the in-process `Azure.Monitor.OpenTelemetry.Exporter` is the higher-fidelity
  escape hatch. Live Metrics does not work through the collector at all.
- **New Relic's packaged AI Monitoring is built around its APM agents, not OTLP** — it keys off
  proprietary event types (`LlmChatCompletionSummary` and similar), and no .NET support is
  documented. Research could not verify that the native AI Monitoring UI reads standard
  `gen_ai.*` OTel attributes. See Revisit When; this is the largest open risk and it lands in
  S13–S15.
- Cardinality discipline moves from "a Log Analytics cost concern" to "a hard per-day limit
  with an error event" — stricter, and the reason for the tenant-annotation rule above.

### Neutral / accepted trade-offs

- Data residency is now a New Relic region choice (US/EU/JP) rather than an Azure region
  choice. It must be decided in S4, not discovered in S6.
- OTLP validation is **asynchronous**: a 2xx does not mean the data was accepted. Silent
  mangling surfaces only as `NrIntegrationError` events, so S4 must include a check on that
  event type. A backend that accepts data and quietly discards part of it is worse than one
  that rejects it.
- NRQL drop rules were closed to new accounts in May 2025 and reach end of life 2026-06-30.
  A new account uses **Pipeline Control**. Anything written about drop rules from older
  material is already obsolete.
- **Azure platform diagnostics are a separate question from application telemetry, and this
  ADR does not settle it.** AKS control-plane logs (now Container Apps environment logs, per ADR-023), APIM diagnostics, and Azure SQL audit logs
  are emitted by Azure resources, not by our code, and they do not travel over OTLP. A minimal
  Log Analytics workspace may still be warranted in S6 for those alone — which is what ADR-007
  and ADR-012 describe when they list Log Analytics in the AKS footprint. **Decide this in S6
  on its own merits**, and do not let it quietly become a second application telemetry backend.

## Alternatives Considered

### Keep Azure Monitor / Application Insights (the status quo)

Deepest integration with the rest of the stack, one vendor, one bill, and no new credential.
Rejected on three grounds: Log Analytics ingestion pricing is materially worse at every scale
this project will reach; Application Insights requires an Azure subscription, which would keep
S4's proof degraded to a local collector until S6; and it leaves ADR-011's vendor-neutrality
claim permanently untested, which for a research-first project is a cost rather than a
neutral.

### New Relic APM agent instead of OpenTelemetry

Least instrumentation effort and the only path that lights up New Relic's packaged AI
Monitoring today. **Rejected, and this rejection is the important one** — it is precisely what
ADR-011 refused, for reasons that have not changed: proprietary instrumentation couples every
file in the codebase to a vendor, at the layer where coupling is most expensive to undo. The
AI Monitoring convenience is not worth re-acquiring that coupling. If AI observability proves
inadequate over OTLP, the answer is a dashboard built on `gen_ai.*` spans, not an agent.

### Grafana Cloud / Honeycomb / Datadog

All accept OTLP and would satisfy the same reasoning. Not compared in depth, because the
decision that matters architecturally is *"a non-Azure OTLP backend, chosen for cost and to
exercise vendor neutrality"* — and any of them is replaceable under this ADR by changing
collector configuration. Recording that replaceability is more useful than ranking them.

### Both backends, in-process, no collector

Rejected on the delta/cumulative temporality conflict described above: one `MeterProvider`
cannot satisfy both preferences. It would also put two vendor credentials into application
configuration and make the secondary backend a redeploy rather than a config change.

## Revisit When

- **New Relic's AI Monitoring is confirmed to read `gen_ai.*` OTLP attributes, or confirmed
  not to.** Re-verify before S13, because this is the one place the decision could prove
  genuinely limiting. The fallback is custom dashboards over standard spans, not an agent.
- Ingest approaches 100 GB/month. The trigger is to design sampling deliberately — tail
  sampling in the collector, keeping all errors and slow traces — not to upgrade reflexively.
- A customer requires telemetry residency in a region New Relic does not offer, or requires
  telemetry to remain inside their own Azure tenancy. Either flips the default back.
- The `azure_monitor` collector exporter leaves beta, or Application Insights-specific
  features become necessary. The in-process exporter is the documented escape hatch.

## Compliance

- **No New Relic SDK, agent, or vendor-specific attribute may appear in application code.**
  Only OTLP and standard OpenTelemetry semantic conventions. This is the boundary that keeps
  ADR-011 true, and it should become an architecture test in the same family as ADR-008's
  provider-SDK ban.
- **`tenant.id` on spans and logs; never as a metric dimension.** Per the rule above.
- **The ingest licence key is a secret** — User Secrets locally, Key Vault via workload
  identity from S6 (Principle V). Never in `appsettings.json`, never in a manifest.
- **S4 must include** collector-side sampling or drop rules, and a check on `NrIntegrationError`
  proving telemetry is accepted rather than silently mangled.
- **S4 proof unchanged**: one tenant operation produces a single correlated trace from entry to
  database. **Gate 1 unchanged**: an induced failure diagnosed from telemetry alone in under
  10 minutes. This ADR changes where the data lands, not what must be provable.

## Note on ADR-001, ADR-011, and `idea.md`

- **ADR-001** grants exactly this kind of exception and requires it be recorded with a reason.
  Its Decision text has been annotated to point here. Azure-first is otherwise unchanged — one
  non-Azure service, one recorded reason.
- **ADR-011** is **refined, not superseded.** Its instrumentation decision — OpenTelemetry
  everywhere, no vendor SDK — is untouched and load-bearing. Only its backend clause changes,
  in exactly the manner its own *Revisit When* prescribed.
- **`idea.md` §17 and §20** still list Azure Monitor, Application Insights, and Log Analytics.
  `idea.md` is product direction and therefore **higher authority than an ADR** (Principle II),
  so this ADR does not amend it. The divergence is recorded as
  [traceability U13](../traceability.md) with a recommendation, following the precedent of U2.
  An agent proposes a blueprint amendment; it does not make one.

**Unverified at the time of writing** — flagged rather than presented as settled: exact metric
cardinality limits (New Relic's docs are circular on the figures; check the in-account limits
UI); whether the 100 GB free grant is per-account or per-organisation; whether New Relic's .NET
OpenTelemetry guidance covers `net10.0` (their example still targets `net8.0`); and current
Azure Log Analytics per-GB pricing, quoted comparatively rather than precisely.
