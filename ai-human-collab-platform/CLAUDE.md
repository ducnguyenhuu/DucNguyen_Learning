# Project Instructions

## Local Dependencies

Service repositories cloned via `/fetch-dependency` are stored in `dependencies/<service-name>/`.
When analyzing or exploring a service's code, check this directory first before fetching remote APIs.

## Available Skills

Run `/help` in Claude Code to see installed skills, or check `.claude/skills/` directory.

### Common Skills

- `/fetch-dependency <service>` - Clone a service repo for local analysis
- `/clean-dependencies` - Remove cloned service repositories
- `/speckit.specify` - Create feature specifications
- `/speckit.plan` - Generate implementation plans
- `/speckit.tasks` - Generate task lists from plans

## Commit Convention

All commits **must** follow [Conventional Commits](https://www.conventionalcommits.org/) format. CI validates this on every push — non-conforming commits will fail the build.

```
<type>(<scope>): <description>
```

**Allowed types:** `feat`, `fix`, `chore`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`
