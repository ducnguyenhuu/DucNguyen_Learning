# ADR-016: Agent-neutral skill location with a tool-specific pointer

**Status**: Accepted
**Date**: 2026-08-08
**Deciders**: Project owner
**Relates to**: `idea.md` §37, §38, §40, §41, §43 · Constitution → Principle II · roadmap S1

## Context

`idea.md` §43 places project-specific custom skills at **`.agent/skills/`**, and §38
explains why: *"The platform should avoid coupling its engineering process to one
specific agent. The agent is replaceable."* §38 names Claude Code, Codex, and GitHub
Copilot as interchangeable executors, and lists skills among the **durable assets**
that outlive any of them.

That reasoning is sound. But it collides with a practical fact: Claude Code discovers
skills in **`.claude/skills/`**. Skills written to `.agent/skills/` are not
auto-discovered, so in practice they would have to be pasted into context manually
every session — which means in practice they would not be used.

This is a real conflict between an architectural principle and a tooling constraint,
and it needs a decision before roadmap S1 writes the seven initial skills.

There is a second, smaller instance of the same pattern already resolved: `idea.md` §43
expected the constitution at `docs/constitution.md`, but Spec Kit reads it from
`.specify/memory/constitution.md`. §58 resolved that by making the tooling location
authoritative and permitting a pointer — not a copy — at the documentation location.
This ADR follows the same shape.

## Decision

**`.agent/skills/` is the source of truth.** Skills are written there, reviewed there,
and versioned there. They are agent-neutral in content: no skill may assume a specific
coding agent, or reference agent-specific commands or file formats.

**`.claude/skills/` is a checked-in symlink to `.agent/skills/`**, so Claude Code
discovers them automatically.

Two consequences worth stating plainly:

- **No duplication.** A copy would drift, and drifted knowledge is worse than absent
  knowledge because it is trusted. The symlink is committed to git.
- **Supporting a second agent means adding a second pointer**, not restructuring or
  copying anything.

The same rule applies to the constitution: `.specify/memory/constitution.md` is
authoritative; `docs/constitution.md` may be a pointer, never a second copy.

## Consequences

### Positive

- `idea.md` §38's agent-neutrality is preserved in substance rather than in name only.
- Claude Code works with zero friction, so the skills will actually be loaded — which
  is the entire point of writing them.
- Adding Codex or Copilot later is one symlink.
- The pattern is now consistent for both cases (skills and constitution), so there is
  one rule to remember rather than two exceptions.

### Negative

- **Symlinks are imperfectly portable.** Git stores them, but Windows requires
  Developer Mode or elevated privileges to check them out correctly, and some CI
  runners and Docker build contexts mishandle them. This is the main risk and it is
  not fully mitigable.
- A second path to the same content can confuse tooling that walks the tree — file
  searches may return duplicate hits.
- Anyone unfamiliar with the arrangement may edit through the symlink path and be
  briefly confused about where the file "really" lives.

### Neutral / accepted trade-offs

- Skills stay agent-neutral in *content*, which rules out writing them in
  agent-specific formats even where that would be convenient.
- Workflow skills — the "HOW we work" layer of §25 and §36 — are **not** covered by
  this ADR. Those are supplied globally by the agent's own skill ecosystem (currently
  the installed `agent-skills` plugin) and are deliberately not vendored into the
  repository. Only the project-specific knowledge skills of §37 and §40 live in
  `.agent/skills/`.

## Alternatives Considered

### Use `.claude/skills/` directly as the source of truth

Simplest, no symlink, no portability risk. Rejected because it concedes §38's
agent-neutrality for a convenience, and because it would put a durable asset (§38's
term) inside a vendor-named directory. If the agent changes, every skill path changes.

### Keep `.agent/skills/` only, reference skills explicitly each session

Most faithful to §38 and requires no symlink. Rejected on realism: manual context
loading every session is friction that will be skipped, and §41's "load only relevant
skills" principle becomes impossible to apply consistently by hand. A skill that is not
loaded has no value.

### Duplicate the files in both locations, synchronised by a script or hook

Avoids symlink portability problems. Rejected because two copies drift, and drifted
architectural guidance is actively harmful — an agent may load the stale copy and cite
it with confidence. This is the same reasoning that made §58 forbid two constitutions.

### A build step that generates `.claude/skills/` from `.agent/skills/`

A cleaner variant of duplication, with generation rather than manual sync. Rejected as
disproportionate: it requires a build step, a gitignore entry, and a stale-output
failure mode, to avoid a symlink. Worth revisiting only if the symlink causes real
problems on Windows or in CI.

## Revisit When

- Symlink handling causes an actual failure on Windows, in CI, or in a container build
  — at which point the generation approach above becomes the fallback.
- A second coding agent is adopted and its discovery mechanism cannot be satisfied by a
  symlink.
- Claude Code gains support for a configurable skills path, which would remove the need
  for the pointer entirely.

## Compliance

Enforced by review rather than automation, which is a known weakness (Principle VII
would prefer a gate):

- `.claude/skills` must remain a symlink, not a directory. A pull request converting it
  to a directory of real files violates this ADR.
- No skill in `.agent/skills/` may reference a specific coding agent by name or assume
  an agent-specific format.
- `docs/constitution.md`, if created, must be a pointer.

A cheap automated check — asserting `.claude/skills` is a symlink and that no skill file
contains an agent-specific marker — would close this and is worth adding to the roadmap
S7 pipeline.
