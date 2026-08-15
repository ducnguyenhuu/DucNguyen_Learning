# ADR-021: Application-layer pattern machinery is adopted at its first real consumer

**Status**: Proposed
**Date**: 2026-08-15
**Deciders**: Duc Nguyen (pending acceptance)
**Relates to**: Constitution Principle IX (final rule) and Principle X (rule 5),
[ADR-002](ADR-002-dotnet-first.md), [ADR-003](ADR-003-service-oriented-architecture.md),
roadmap S9 and S11

## Context

Two patterns were raised for use in upcoming slices: **FluentValidation** for input
validation, and **CQRS**. Neither appears anywhere in the codebase, the specs, the ADRs, or
the skills today, so no recorded decision governed them — which is why this ADR exists
rather than a code change.

The question is not whether either pattern is good. Both are well established. The
question the Constitution actually asks is *which slice has a consumer for it*.
Principle X rule 5 is explicit: "A slice MUST NOT build capability for anticipated future
needs. Where a future need is foreseen, the seam is created and the implementation
deferred." Principle IX's rationale names this failure mode as "the one most likely to be
violated by **enthusiasm**", and this ADR was prompted by exactly that impulse, honestly
stated.

"CQRS" also needs disambiguating before it can be decided, because it names three
different things and one of them is already in place. S2 shipped one class per use case —
`CreateTenant`, `GetTenant`, `RenameTenant`, `ListTenants`, `ListMembers`, `RemoveMember`,
`ChangeMemberRole`, `InviteMember`, `AcceptInvitation`, `ListInvitations`,
`RevokeInvitation`. Commands and queries are already separate types. What is absent is a
mediator and a distinct read model, and those are separate questions with different
answers.

## Decision

We adopt application-layer pattern machinery at its first real consumer, never in
anticipation. Concretely, three rulings a reader can check a change against:

1. **Validation stays in the domain.** Invariants are enforced by guard clauses on
   aggregates and value objects throwing `DomainException`, mapped to HTTP status codes at
   the endpoint. **No validation library is added.** A validation library would not replace
   these guards — the domain must protect itself regardless of caller — so it can only ever
   be an additional boundary layer, and today's request DTOs carry one or two fields.

2. **"CQRS" in this codebase means one class per use case, and that is satisfied.** No
   mediator, dispatcher, or `ISender`-style indirection is introduced. Cross-cutting
   concerns are handled where they arise: HTTP concerns in `IEndpointFilter`
   (`IdempotencyFilter`, tenant-context resolution, `RequireTenantAdministrator`),
   persistence concerns in EF Core interceptors and global query filters.

3. **No separate read model.** The write model serves reads. Projections are a real need
   in the Delivery context, but that context does not exist yet.

## Consequences

### Positive

- No dependency, licence, or upgrade obligation is taken on for a pattern with no consumer.
  This matters concretely for mediator libraries in the .NET ecosystem, where licensing
  terms have changed in recent years.
- The two patterns get evaluated against a real input surface (S9's connector
  configuration) and a real read path (S11's projections) rather than against `{displayName}`.
- A wrong call is cheap. Adopting at S9 and regretting it discards a slice's worth of
  code; adopting now and regretting it at S9 means refactoring six slices.

### Negative

- **Validation errors continue to surface one at a time.** Guard clauses fail on the first
  problem, so a client submitting three bad fields learns about one. A validation library
  returns all of them at once, and that is a genuine API-quality loss we are accepting for
  now.
- **Validation rules stay split between the domain and the database schema, with nothing
  keeping them aligned.** This is not theoretical: `Tenant.EnsureValidDisplayName` checks
  only `IsNullOrWhiteSpace`, while `TenantConfiguration` sets `HasMaxLength(200)`. A
  201-character display name passes the domain, reaches the database, and surfaces as a
  `500`. Deferring the library does not excuse this gap; it must be closed with a guard
  clause.
- **Learning these patterns is postponed**, which is a real cost given this project's
  stated purpose. The mitigation is that both patterns remain on the roadmap with named
  slices, not abandoned.

### Neutral / accepted trade-offs

- Ruling 2 means this codebase is "CQRS" by the term's original definition and not by its
  common .NET usage, where CQRS and MediatR are often conflated. Expect to explain this.
- Endpoints keep mapping domain exceptions to status codes by hand, so each new endpoint
  must remember to do so. That convention is currently unenforced — see Compliance.

## Alternatives Considered

### Adopt FluentValidation now, in S3

Would establish one validation idiom before more endpoints exist, avoiding a later
migration, and closes the "one error at a time" weakness immediately. Rejected because S3
is architecture tests: it introduces no request DTOs at all, so the library would land with
zero consumers and its first real exercise would still be S9. Adding it now optimises for
consistency with code not yet written.

### Adopt a mediator (MediatR-style) for command/query dispatch

Its main draw is pipeline behaviours giving uniform logging, validation, and transaction
handling. Rejected because this codebase already places those concerns deliberately —
HTTP-level ones in endpoint filters, persistence-level ones in interceptors — and those are
the more accurate homes for them. Introducing a dispatcher to gain a pipeline this
architecture already has would be Principle IX's "router with one route".

### Write two ADRs, one per pattern

Considered, and the template does warn that a decision needing lots of explanation is
probably two decisions. Rejected because the operative decision here is a single stance —
defer machinery to its first consumer — and the two patterns are worked examples of it.
Splitting would duplicate the rationale and let the two copies drift.

### Commit now to adopting each pattern at a named slice

Tempting, and close to what prompted this ADR. Rejected because it is the error this
directory's own README warns against: "recording decisions before the information needed to
make them exists." We do not yet know S9's input surface or S11's read shapes. The
adoption points below are therefore revisit triggers, not commitments.

## Revisit When

Any one of these is a trigger to reopen the corresponding ruling:

- **Validation (ruling 1)** — a single request DTO reaches roughly five or more fields, or
  carries conditional rules where one field's validity depends on another. S9's per-tenant
  connector configuration (credentials, endpoint, project keys, field mappings) is the
  foreseen case; S13's structured-model-output contract is the second.
- **Mediator (ruling 2)** — a cross-cutting concern appears that is genuinely neither an
  HTTP concern nor a persistence concern, and so has no correct home in a filter or an
  interceptor.
- **Read model (ruling 3)** — a read path needs data shaped differently from how it is
  written. S11's canonical projections over S9's raw landing store is the foreseen case,
  and roadmap S11 already describes projections; adopting read models there is expected to
  be a confirmation of that plan rather than a new direction.

## Compliance

Rulings 1 and 2 are enforceable by an automated gate and should be: the absence of a
validation-library or mediator package reference is checkable in the same way roadmap S3's
architecture tests check for a provider SDK. Adding the two package-name checks to S3's
gate set is the intended enforcement, and until that lands, these rulings rest on human
review.

Ruling 3 is not mechanically checkable in any useful way while only one context exists,
and is enforced by review.

The unenforced convention noted under Neutral consequences — that every endpoint must map
`DomainException` to a 4xx status — is a known weakness, not a neutral fact.
`ProblemDetailsHandler` maps every uncaught exception to `500`, so an endpoint that forgets
the mapping turns a client's bad input into a server error silently. This is a candidate
gate for roadmap S3 and is recorded here because this ADR's ruling 1 is what leaves the
convention load-bearing.
