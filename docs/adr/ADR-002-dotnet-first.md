# ADR-002: .NET and C# as the primary stack

**Status**: Accepted
**Date**: 2026-08-08
**Deciders**: Project owner
**Relates to**: Constitution → Technology Constraints · `idea.md` §13, §21, §44 item 2

## Context

The platform is a service-oriented enterprise SaaS system that must support
Domain-Driven Design, Clean Architecture, automated architecture governance, strong
typing across service boundaries, and first-class OpenTelemetry instrumentation
(`idea.md` §21–22). It runs on Azure (ADR-001) and integrates with Microsoft-centric
enterprise systems.

The research objective adds a constraint that would otherwise be secondary: roadmap
S3 requires *automated* architecture tests that fail the build on boundary
violations. That capability is much stronger in some ecosystems than others, and it
is not optional here — Constitution Principle VII depends on it.

## Decision

We use **.NET (current LTS), C#, and ASP.NET Core** as the primary application stack
for all backend services.

This settles: Entity Framework Core for relational persistence, xUnit for testing,
NetArchTest or ArchUnitNET for architecture tests, and the .NET OpenTelemetry SDK for
instrumentation.

Other languages may appear for genuinely different jobs — infrastructure is HCL
(ADR-012), scripting is shell — but no second general-purpose backend language is
introduced without its own ADR.

## Consequences

### Positive

- Static typing and a mature nullable-reference model catch a large class of the
  errors that tenant-isolation code cannot afford to make (Principle IV).
- Architecture testing is a solved problem in .NET. NetArchTest and ArchUnitNET make
  Principle VII's "boundary violations fail the build" straightforward rather than
  bespoke.
- Best-in-class Azure SDK support: managed identity, Key Vault, Service Bus, and
  Application Insights all have well-maintained first-party libraries, which directly
  reduces the cost of ADR-001's consequences.
- Clean Architecture and DDD have deep, well-documented precedent in .NET, so the
  layering that Principle III mandates is idiomatic rather than imposed.

### Negative

- **The AI and data-science ecosystem is markedly weaker than Python's.** This is the
  real cost. Embeddings, evaluation tooling, and retrieval libraries are all more
  mature in Python. Roadmap S15 (AI evaluation) is where this will hurt most, and it
  may require either building more ourselves or accepting a Python sidecar later.
- Container images are larger and cold starts slower than Go or Rust equivalents.
  Roadmap S5 records a baseline specifically so this is measured rather than assumed.
- Smaller open-source surface for delivery-analytics and integration libraries than
  the JVM or Python ecosystems.

### Neutral / accepted trade-offs

- Committing to LTS releases means deliberately lagging the newest language features
  in exchange for support duration.
- A future Python component for AI evaluation or embeddings would not violate this
  ADR provided it sits behind a service boundary (Principle III) and is introduced by
  its own ADR. This is the most likely amendment.

## Alternatives Considered

### Python (FastAPI)

Strongest candidate, and genuinely competitive. It would make the entire AI half of
the roadmap — S13 through S15 and all of Horizon 3 Track B — easier, with better
libraries for embeddings, retrieval, and evaluation.

Rejected on the enterprise half rather than the AI half. Architecture governance
tooling is weaker, static typing is optional and therefore unreliable at boundaries,
and the DDD/Clean Architecture precedent is thinner. Given that Horizon 1 is eight
slices of enterprise foundation and the AI work does not begin until S13, optimising
for the AI phase at the expense of the foundation would be optimising for the part
that starts fifth.

### Java / Kotlin with Spring Boot

Comparable enterprise maturity, excellent architecture-test tooling (ArchUnit is the
tool NetArchTest imitates), and strong DDD precedent. Rejected on Azure alignment:
the Azure SDK and Entra ID integration story is materially better in .NET, and
ADR-001 already committed to Azure. Choosing Java would mean fighting that seam
throughout.

### TypeScript / Node

Rejected. Adequate typing, but the weakest of the four for architecture governance,
DDD structure at scale, and enterprise identity integration. Its main advantage —
sharing a language with a future frontend — is not worth the backend cost, and no
frontend is in the MVP scope (`idea.md` §46a).

### Go

Excellent operational characteristics: small images, fast starts, strong concurrency.
Rejected because DDD and Clean Architecture layering is unidiomatic in Go, the
architecture-governance tooling is immature, and the Azure SDK support is second-tier.
The operational wins do not matter at the scale this platform targets in Horizons 1–2.

## Revisit When

- Roadmap S15 (AI evaluation) proves impractical in .NET — the most likely trigger.
  The expected outcome is not replacing .NET but adding a Python service behind a
  boundary, via a new ADR.
- Container size or cold start measurably harms operations against the S5 baseline.
- A hiring or contribution constraint makes C# a liability.

## Compliance

Enforced automatically from roadmap S3 onward:

- Architecture tests assert the layering this stack enables (domain does not depend
  on infrastructure).
- The build fails on compiler warnings-as-errors and nullable-reference violations.
- Introducing a second general-purpose backend language would require a new project
  file and a pipeline change, both conspicuous in review.
