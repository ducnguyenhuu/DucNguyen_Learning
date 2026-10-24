# AI Engineering & Delivery Intelligence Platform

An intelligence layer over the engineering systems an organisation already uses — Jira,
Azure DevOps, GitHub — that answers **"why is my project yellow?"** with evidence,
contributing factors, and recommended actions.

It does not replace those systems. It explains what they contain.

## Status

**Pre-code.** Slice 1 of 15 (constitution, ADRs, repository foundation) is complete.
Slice 2 — authentication, membership, and persistence — is specified and next. No
application code exists yet.

## Start here

| If you want to know… | Read |
|---|---|
| **What to do next** | [roadmap.md](roadmap.md) — page 1 only |
| The vision and the reasoning | [idea.md](idea.md) |
| The rules all work must follow | [Constitution](.specify/memory/constitution.md) — 11 principles (IV retired, ADR-025) |
| Why a technical choice was made | [docs/adr/](docs/adr/) — 10 decisions |
| If anything from the blueprint was missed | [docs/traceability.md](docs/traceability.md) |
| Instructions for an AI coding agent | [AGENTS.md](AGENTS.md) |

## The plan, in short

**15 pieces of work, done one at a time**, in two groups separated by a gate that can be
failed.

**Foundation (8)** — login and membership, architecture tests, observability, containers,
Terraform to Azure, CI/CD, messaging.
→ *Gate 1: can a change reach Azure in under 20 minutes with no manual step?*

**Real data and first AI (7)** — connect a real Jira project, sync it, normalize it,
score project health deterministically, then add one AI capability that explains the
score.
→ *Gate 2: does a real Delivery Manager say **"yes, and I didn't know that"**?*

Gate 2 is designed to be failable. If the answer is *"I already knew that"*, the product
premise is wrong and it is worth far more to discover that at month 7 than at month 24.

Anything after Gate 2 is deliberately undecided.

## Two products in one repository

Per [idea.md §54](idea.md): the platform itself, and the AI-assisted engineering system
that builds it — specifications, constitution, ADRs, skills, tests, and verification.
Product B builds Product A, and what is learned building A improves B.

## Technology

.NET · Azure · Container Apps · Terraform · Azure SQL · Service Bus · Entra ID · OpenTelemetry

Each choice is recorded with its alternatives and its costs in [docs/adr/](docs/adr/).

## Contributing

Commits follow [Conventional Commits](https://www.conventionalcommits.org/) and CI
enforces it. Read the [Constitution](.specify/memory/constitution.md) before your first
change — in particular Principle II, which states that when a skill or plan conflicts
with an ADR, the ADR wins, and that a decision believed wrong should be **proposed as a
change rather than worked around**.
