# ADR-NNN: [Short decision title, stated as the decision not the question]

**Status**: Proposed | Accepted | Superseded by ADR-NNN | Deprecated
**Date**: YYYY-MM-DD
**Deciders**: [who accepted this]
**Relates to**: [Constitution principle, roadmap slice, other ADRs, idea.md section]

## Context

What forces are at play? What makes this decision necessary *now*? State the
constraints honestly, including the ones that are uncomfortable — cost, deadline,
skill gaps, existing commitments.

Two or three paragraphs. If it needs more, the decision is probably two decisions.

## Decision

State it in the active voice, as something now true: "We use X." Not "We should
use X" or "X was chosen."

Be specific enough that a reader can tell whether a given change complies.

## Consequences

### Positive

- What becomes easier or possible.

### Negative

- What becomes harder, slower, or more expensive. **Do not skip this section.**
  An ADR with no negative consequences is either dishonest or describing something
  that was not a decision.

### Neutral / accepted trade-offs

- Things that are neither good nor bad but that follow from the decision and should
  not surprise anyone later.

## Alternatives Considered

### [Alternative 1]

What it was, and **why it was rejected**. Be fair to it — a strawman here is worse
than no entry, because it hides the fact that the alternative was never seriously
weighed.

### [Alternative 2]

As above.

## Revisit When

Under what future conditions should this decision be reopened? A concrete trigger —
"when we exceed N tenants", "when a second AI consumer appears", "if monthly cost
exceeds X" — is far more useful than "periodically".

Leaving this blank asserts the decision is permanent. Very few are.

## Compliance

How is this decision enforced? Prefer an automated gate (Constitution Principle VII).
If it can only be enforced by human review, say so explicitly — that is a known
weakness, not a neutral fact.
