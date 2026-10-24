# Project Knowledge Skills

**What these are:** project-specific knowledge — reusable knowledge + instructions +
constraints + patterns (`idea.md` §37). A skill is not an agent and does not act.

**What these are not:** workflow practices. "How to work" — TDD, debugging, code
review, planning — comes from the coding agent's own skill ecosystem (`idea.md` §25,
§36) and is deliberately not vendored here.

## Location

`.agent/skills/` is the source of truth. `.claude/skills` is a **symlink** to this
directory so Claude Code discovers them. Adding another agent means adding another
pointer, never a copy. See [ADR-016](../../docs/adr/ADR-016-agent-neutral-skill-location.md).

Skill *content* must stay agent-neutral: no skill may name a specific coding agent or
assume agent-specific commands. The `SKILL.md` filename and its two frontmatter fields
are the minimum needed for discovery and are treated as a generic convention.

## The seven initial skills

Only seven, per `idea.md` §55 Step 8. §37 lists 12 and §40 lists 13 — those are full
inventories, not the current scope. **Add a domain skill when its domain is actually
implemented**, not in anticipation.

| Skill | Load it when |
|-------|-------------|
| `architecture` | Making a structural decision, or checking a boundary |
| `dotnet-enterprise` | Writing any .NET code |
| `azure-architecture` | Touching Azure resources or Terraform |
| `distributed-systems` | Messaging, retries, idempotency, consistency |
| `testing` | Writing tests, or deciding what to test |
| `security` | Auth, membership, secrets, or any untrusted input |
| `ai-engineering` | Anything involving a model (slice 13 onward) |

**Load only what the task needs** (`idea.md` §41). Loading all seven wastes context and
creates conflicting instructions.

## Not yet written

`api-design` · `event-driven` · `observability` · `terraform` ·
`delivery-management` · `engineering-management`

Each arrives with its domain. Do not create a `enterprise-everything` skill (§40).
