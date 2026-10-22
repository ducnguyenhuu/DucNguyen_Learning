# ADR-008: AI Gateway built in stages, abstraction seam first

**Status**: Accepted
**Date**: 2026-08-08
**Deciders**: Project owner
**Relates to**: Constitution → Principle IX · `idea.md` §8, §9, §9a, §57.3 · roadmap S13

## Context

`idea.md` §9 assigns the AI Gateway eleven responsibilities: provider abstraction,
model selection, prompt execution, context, tools, policies, cost, observability,
rate limits, security, and evaluation. §8 additionally places a Model Router and an
Agent Runtime alongside it.

Building all of that before a consumer exists would be substantial work — several
slices at minimum — validated by nothing. A router with one route is not a router;
it is indirection with a configuration file. Rate limits with one caller cannot be
tuned. An evaluation harness with no capability to evaluate has no test data.

`idea.md` §14 already prohibits this pattern for services: *"We will not create
microservices merely because we can."* The same discipline was not originally applied
to the gateway, and §9a was added to correct that.

The countervailing risk is real and must not be traded away: if business logic calls
a model provider directly even once, the coupling spreads, and retrofitting an
abstraction after several call sites exist is expensive. The seam is the part that
cannot be deferred.

## Decision

We build the AI Gateway in **two stages**, and we establish the **abstraction seam
from the first line of AI code**.

**Stage 1** — built in roadmap S13, together with its first consumer (S14):

- Provider abstraction (the seam)
- Prompt execution and prompt management with versioning
- Token counting and cost attribution per tenant and per capability
- AI telemetry: model, latency, tokens, cost, outcome

**Stage 2** — built only when a second, materially different consumer exists:

- Model routing and model selection
- Policies
- Rate limits
- Evaluation harness *(note: a capability-specific evaluation harness arrives earlier,
  at S15; Stage 2's is the generalised, multi-capability form)*
- Tool orchestration

**Binding rule: no gateway capability is built until a named consumer requires it.**
"We will need it eventually" is not a named consumer.

**Non-negotiable regardless of stage:** business services consume AI only through the
abstraction. A direct provider call from business logic is prohibited and fails the
build (Principle IX, enforced by architecture test from S3 onward).

## Consequences

### Positive

- S13 becomes one slice instead of four or five, which is what makes reaching Gate 2
  in Horizon 2 feasible at all.
- Every capability that does get built has a real consumer shaping it, so its design
  is validated rather than imagined.
- The seam existing from day one means Stage 2 is an internal change behind a stable
  interface — callers do not change when routing appears.
- Cost attribution from the very first invocation means AI spend is never
  retroactively unattributable, which Principle IX requires.

### Negative

- **The interface will need revision when Stage 2 arrives.** A capability-based
  interface designed against one provider will have absorbed assumptions from that
  provider. Some churn is certain; the seam limits its blast radius but does not
  eliminate it.
- Adding a second provider later is more work than designing for two from the start
  would have been — we are paying later for what we save now, and accepting that the
  saving is worth more because it is certain while the later cost is contingent.
- Deliberately shipping a gateway that does not match `idea.md` §9's description
  creates a documentation gap between blueprint and reality, mitigated only by §9a
  and this ADR being explicit about it.

### Neutral / accepted trade-offs

- The Agent Runtime from §8 is not part of either stage. It belongs to Horizon 3
  Track C and has no consumer until agents exist.
- "Security" from §9's list is not a distinct gateway feature; it is satisfied by
  Principles IV and V applying to the gateway as to everything else. Tenant isolation
  of AI context is Principle IV's concern, not a gateway responsibility to invent.
- Stage 1 has exactly one provider. This is not a limitation to work around; it is
  the decision.

## Alternatives Considered

### Build the full §9 gateway before any consumer

The blueprint's original reading. Rejected as speculative generality: it would
consume most of Horizon 2's budget producing components validated by nothing, and
push Gate 2 — the only test that can falsify the product premise — months later. The
longer Gate 2 is deferred, the more work rests on an unverified assumption.

### No gateway at all — call the provider directly, abstract later

Fastest to a working AI feature, and superficially consistent with "build only what
has a consumer."

Rejected because it trades away the one thing that genuinely cannot be retrofitted
cheaply. Provider SDK types leak into domain code, prompt handling scatters across
call sites, and cost tracking becomes impossible to add consistently. The seam costs
little to establish and a great deal to introduce late — the opposite profile from
the routing machinery.

### Adopt a third-party AI gateway product

Would provide routing, cost tracking, and rate limits immediately. Rejected for
Horizon 2 on two grounds: it introduces a dependency at the most sensitive point for
tenant isolation of AI context (Principle IV), and the research objective in
`idea.md` §52 explicitly lists model routing and evaluation as things to *learn*, not
to outsource. Worth reconsidering in Horizon 3 Track A if routing proves harder than
expected.

## Revisit When

- **A second materially different AI consumer appears.** This is the trigger for
  Stage 2, and it should be a deliberate decision at that moment, not a drift.
- Cost or quality problems demand routing before a second consumer exists — a
  legitimate early trigger, since Principle VIII requires model choice to be measured.
- A tenant requires a specific provider or a private model, which forces routing
  regardless of consumer count.

## Compliance

- **Architecture test (from S3):** no assembly outside the AI Platform may reference a
  model provider SDK. This is the load-bearing gate.
- **Architecture test:** business services reference only the AI capability contract
  assembly.
- Every invocation records tenant, capability, model, tokens, cost, latency
  (roadmap S13 proof).
- Stage 2 work requires naming its consumer in the pull request. A Stage 2 capability
  merged without a named consumer violates this ADR and should be reverted.
