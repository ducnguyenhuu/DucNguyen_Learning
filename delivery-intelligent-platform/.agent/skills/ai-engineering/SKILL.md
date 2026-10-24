---
name: ai-engineering
description: Use when proposing, designing, or reviewing anything that involves an AI model or LLM — deciding whether AI is warranted at all, defining a capability contract, or touching structured output, grounding, cost tracking, or evaluation. Relevant from slice 13 onward.
---

# AI Engineering

Governed by [Constitution Principles VIII and IX](../../../.specify/memory/constitution.md),
[ADR-008](../../../docs/adr/ADR-008-ai-gateway-staged.md),
[ADR-009](../../../docs/adr/ADR-009-capability-based-model-abstraction.md).

## First question: should this use AI at all?

`idea.md` §49's gate, and it is a real gate:

```
Can deterministic logic solve this?
   YES → use deterministic logic. Stop here.
   NO  → Does AI provide meaningful, measurable value?
            NO  → do not use AI
            YES → evaluate quality, cost, latency, security, grounding, observability
```

Most "AI features" fail at the first question. **"LLM everywhere" is explicitly rejected**
— it produces systems that are slower, costlier, non-reproducible, and untestable.

## The line that matters most in this product

**Scoring is arithmetic. AI explains it.**

- *"Is this project yellow?"* → deterministic computation over metrics. Reproducible,
  auditable, cheap, testable. **Slice 12, no AI.**
- *"Why is this project yellow?"* → reasoning over context. **Slice 14, AI.**

Putting an LLM in the scoring path makes the score non-reproducible and unauditable, and
it is the mistake this project is most likely to make because it feels like progress.
`idea.md` §57.4 records why the roadmap was resequenced to prevent it.

## Capabilities, never model names

Callers request `ReleaseRiskAnalysis`, not `gpt-4o` (ADR-009). A capability owns its
prompt, output schema, and quality expectations. Model selection is **configuration**
inside the AI Platform, changeable without touching any consumer.

**A model name string outside AI Platform configuration is a build failure.** So is a
provider SDK reference from business logic (ADR-008's architecture test).

## What exists in Horizon 2

Stage 1 only (ADR-008): provider abstraction, prompt execution and versioning, token and
cost tracking, telemetry. **One** provider.

**Not built:** model routing, policies, rate limits, tool orchestration, agent runtime.
None has a consumer. Do not build a gateway capability without naming its consumer — and
"we will need it eventually" is not a consumer.

## Structured output

- Define the output schema; validate every response against it.
- **Reject malformed output safely.** Never let unvalidated model output flow into the
  domain.
- Treat model output as untrusted input, because it is.

## Grounding

Every factual claim traceable to specific ingested data, and the grounding
**inspectable** by the user.

**When data is insufficient, the system declines.** It does not invent. Slice 14's proof
requires demonstrating this with deliberately inadequate data — a system that always
answers is a system that sometimes confabulates.

## Cost accountability

Every invocation records: caller, capability, model, tokens, cost, latency, outcome
(Principle IX). Without this, `idea.md` §11's measured model comparison and Gate 2's
"cost per insight is known" are both impossible.

Emit these as **standard `gen_ai.*` OpenTelemetry attributes on spans** — `gen_ai.system`,
`gen_ai.request.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`. Cost is
not in the semantic convention, so compute it yourself.

**Known risk, verify before building** ([ADR-018](../../../docs/adr/ADR-018-new-relic-telemetry-backend.md)):
New Relic's packaged AI Monitoring is built around its APM agents and proprietary event types,
and it is **not confirmed** to read `gen_ai.*` OTLP attributes. Do not assume the vendor UI
lights up. If it does not, the answer is a dashboard over standard spans — **not** a vendor
agent, which ADR-011 rejected for coupling reasons that have not changed.

## Model choice is measured, not preferred

`idea.md` §11: **self-hosted is not automatically cheaper.** Before claiming it, compare
quality, GPU cost, utilization, latency, operational cost, security, and availability
against managed models.

This is Horizon 3 Track A, and it is a non-goal until managed models have been measured
first (§46a).

## Evaluation

Slice 15. Build an evaluation dataset from real projects with known outcomes, score
quality dimensions (grounded, accurate, useful, non-contradictory), detect regressions
between prompt versions, and run it in CI.

Gate 2 requires a quality score you would be willing to show someone else. Impressions do
not count.

**Note:** .NET's AI evaluation ecosystem is weaker than Python's — ADR-002 records this as
the most likely trigger for adding a Python service behind a boundary. Expect friction
here, and raise it rather than working around it.

## Rationalizations that mean AI is about to go where it shouldn't

| Thought | Reality |
|---------|---------|
| "An LLM call is quick to prototype, we can swap it for logic later" | The "later" swap rarely happens once a demo works — and if it's arithmetic, deterministic logic was never actually slower to write. |
| "This score contributes just a little AI judgment on top of the math" | Any AI contribution to the score makes the whole score non-reproducible and unauditable. There's no "a little" — see why the roadmap was resequenced in `idea.md` §57.4. |
| "The model output looks well-formed, validating it is redundant here" | Model output is untrusted input by definition, regardless of how clean a specific response looks. Skipping validation once is how a malformed response reaches the domain the one time it isn't clean. |
| "We're confident in the answer even though the ingested data is thin" | Confidence isn't grounding. If the data can't support the claim, the system must decline — an always-answering system sometimes confabulates, which is worse than declining. |
| "It's just a model name in this one call site, we'll clean it up" | A model name outside AI Platform configuration is a build failure by design (ADR-008's architecture test), specifically because "just this once" is how routing logic ends up scattered across call sites. |
| "We'll add cost/telemetry tracking once this capability is used more" | Without per-invocation cost tracking from day one, `idea.md` §11's model comparison and Gate 2's "cost per insight is known" become retroactively impossible to answer. |

## Red flags — stop and re-check

- A model name string outside AI Platform configuration
- AI output feeding directly into a score, threshold, or classification
- Model output consumed without schema validation
- A factual claim with no traceable grounding in ingested data
- A new capability added with no defined consumer, "for when we need it"
- An AI feature shipped with no quality metric anyone would show someone else

**All of these mean: stop, re-run the first-question gate (deterministic logic first), and don't ship until grounding, validation, and cost tracking are actually in place.**

## Anti-patterns

- AI computing a score, a threshold, or a classification that arithmetic could produce
- A model name in business logic
- Consuming model output without schema validation
- Ungrounded claims presented as fact
- Building routing with one route, or rate limits with one caller
- Prompts scattered across call sites instead of owned by a capability
- An AI feature with no way to measure whether it is any good
