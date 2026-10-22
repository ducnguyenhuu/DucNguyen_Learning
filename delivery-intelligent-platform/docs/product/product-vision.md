# Product Vision

**This document is a pointer, not a copy.** `idea.md` §55 Step 2 asked for a product
vision document. The content already exists in `idea.md` — duplicating it here would
create two sources of truth, which Constitution Principle II exists to prevent. This
page tells you where each part lives.

See [traceability U1](../traceability.md#u1--55-steps-2-4-and-6-require-five-documents-that-roadmap-s1-does-not-list).

## Vision

> The platform is an **intelligence layer** across existing enterprise engineering
> systems — it does not replace Jira, Azure DevOps, GitHub, ServiceNow, or PagerDuty.
> — [`idea.md` §3](../../idea.md)

The ambition, stated as a question the product must answer:

> **"Why is my project yellow?"** — with evidence, contributing factors, forecast, and
> recommended actions. Not just *"Project = Yellow"*. — `idea.md` §6

## Where each part is defined

| Topic | Location |
|-------|----------|
| Product vision and the anti-replacement stance | `idea.md` §3 |
| The five personas and their needs | `idea.md` §4 |
| Product domains | `idea.md` §5 |
| Delivery Intelligence ambition | `idea.md` §6 |
| Engineering Intelligence ambition | `idea.md` §7 |
| **MVP scope, cut line, and non-goals** | `idea.md` §46a |
| MVP exit criterion, operatively | `roadmap.md` Gate 2 |
| Priorities and sequence | [`roadmap.md`](../../roadmap.md) page 1 |
| What each delivery concept actually is | [domain-model.md](../architecture/domain-model.md) |

## MVP, in one paragraph

The MVP serves **one persona — the Delivery Manager** — and one question. A Delivery
Manager connects their real Jira or Azure DevOps project, sees which projects are at
risk, and gets an evidence-backed explanation of *why*.

It succeeds if they say **"yes, and I didn't know that."** It fails if they say *"I
already knew that"* or *"that's wrong"* — regardless of how much was built.

Engineering Manager, Architect, SRE, and Executive are post-MVP. The architecture must
not block them; no MVP feature exists for them.

## Note on §4

`idea.md` §4 lists needs for all five personas and reads like a commitment to all of
them. **§46a governs**: only the Delivery Manager is in the MVP. §4 is the full persona
inventory, not the MVP scope.
