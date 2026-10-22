# ADR-009: Capability-based model abstraction

**Status**: Accepted
**Date**: 2026-08-08
**Deciders**: Project owner
**Relates to**: Constitution → Principle IX · `idea.md` §10, §11, §44 item 9 · roadmap S13, Horizon 3 Track A

## Context

Model providers, prices, context windows, and capabilities change faster than this
platform's release cycle. A model name embedded in business logic becomes a migration
project the moment that model is deprecated, repriced, or outperformed.

`idea.md` §10 states the requirement: *"Applications should request capabilities
rather than hard-code models."* §11 adds a related constraint about self-hosted
inference — that Llama must not be assumed cheaper than managed models, and that
model choice must be *measured* across quality, GPU cost, utilization, latency,
operational cost, security, and availability.

Both point at the same design: the caller must not know or care which model runs.

## Decision

Callers request a **named capability**, never a model.

A capability is a stable, business-meaningful identifier — `ReleaseRiskAnalysis`,
`ProjectHealthNarrative`, `DependencyImpactSummary` — that declares *what is needed*,
not *how it is served*. Each capability owns its prompt, its expected output schema,
and its quality and cost expectations.

**Model selection is configuration, not code.** Mapping a capability to a model is
made in configuration owned by the AI Platform, changeable without touching or
redeploying any consumer.

**Model choice is decided by measurement.** Per Principle VIII, adopting or switching
a model for a capability requires comparing quality, cost, latency, security, and
grounding. Self-hosted inference must additionally account for GPU cost, utilization,
and operational cost before any claim that it is cheaper (`idea.md` §11).

In Horizon 2 there is exactly **one** provider and a trivial capability→model map.
That is not a violation of this ADR — the abstraction's value is that adding the
second provider changes no consumer.

## Consequences

### Positive

- Swapping a model is a configuration change, tested by the S15 evaluation harness
  rather than by a code review.
- Cost and quality become attributable **per capability**, which is what makes
  Principle IX's cost accountability and §11's measured comparison possible at all.
- Different capabilities may use different models — a cheap model for summarization,
  a stronger one for reasoning — without any consumer knowing.
- Horizon 3 Track A's Llama-versus-managed comparison becomes an experiment run
  behind the seam, not a re-architecture.

### Negative

- **Capability granularity is a judgement call with no obvious right answer.** Too
  coarse and model selection cannot be tuned usefully; too fine and there is a
  capability per prompt and the abstraction adds ceremony without benefit. Expect to
  get this wrong initially.
- The abstraction can hide provider-specific features worth using — structured output
  modes, prompt caching, extended thinking. Reaching them requires either leaking
  provider concepts into the capability contract or forgoing them.
- An indirection layer to debug through when output is wrong: is the fault the prompt,
  the capability contract, the mapping, or the model?

### Neutral / accepted trade-offs

- Capability names become a public contract inside the codebase. Renaming one is a
  breaking change, so they should be named for the business need rather than the
  current implementation.
- Prompts are versioned with the capability, not with the consumer, which means a
  prompt change affects all callers of that capability simultaneously. This is
  intended — it keeps evaluation meaningful.

## Alternatives Considered

### Callers name the model directly

Simplest, and honest about what is happening in Horizon 2 where only one model exists.
Rejected because it makes every model change a code change across every call site,
and because it makes per-capability cost and quality measurement impossible — which
would leave both `idea.md` §11 and Principle VIII unimplementable.

### Callers name a model *tier* (fast / balanced / strong)

A middle option: abstracts the specific model but not the shape of the request. It is
simpler than capabilities and genuinely useful.

Rejected as the primary abstraction because a tier carries no prompt, no output
schema, and no quality expectation — so prompts scatter back to call sites and
per-capability evaluation is lost. Tiers may still appear *inside* the capability→model
mapping as an implementation convenience.

### An off-the-shelf model gateway or router

Would provide capability routing immediately. Rejected for the same reasons as in
ADR-008: dependency risk at the tenant-isolation boundary, and `idea.md` §52 lists
model routing as something to learn rather than outsource. Reconsider in Track A.

## Revisit When

- Capability granularity proves wrong in practice — recurring awkwardness is evidence
  the boundary is misplaced, and per Principle II it should be moved rather than
  worked around.
- A provider-specific feature delivers enough value to justify leaking it into the
  contract. Record that as a new ADR rather than an exception.
- Horizon 3 Track A's measurements show routing needs are materially different from
  what this design assumed.

## Compliance

- **Architecture test:** no consumer assembly references a provider SDK or a model
  identifier string (ADR-008's gate, same mechanism).
- Capability→model mapping lives in AI Platform configuration; a model name appearing
  in a consumer's source is a build failure.
- Roadmap S13 proof requires every invocation to record tenant, capability, model,
  tokens, cost, and latency — without which the measurement this ADR mandates is not
  possible.
